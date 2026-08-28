#!/usr/bin/env python3
"""Daily Slack report for OUTCOME_APP_PROMOTION campaigns (yesterday, US/Eastern)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import REPORT_TIMEZONE, Config
from meta_client import MetaClient
from slack_notifier import SlackNotifier

INSTALL_ACTION_TYPES = {
    "mobile_app_install",
    "omni_app_install",
    "app_install",
    "offsite_conversion.fb_mobile_app_install",
    "offsite_conversion.fb_pixel_custom.app_install",
}

# Meta often returns both omni_app_install and mobile_app_install with the
# same count — use one canonical type (matches Ads Manager app installs).
INSTALL_COUNT_PRIORITY = (
    "omni_app_install",
    "mobile_app_install",
    "app_install",
    "offsite_conversion.fb_mobile_app_install",
    "offsite_conversion.fb_pixel_custom.app_install",
)

HIGH_CPI_AD_THRESHOLD = 8.0
# Ad must have spent on at least this many days in the 7-day window.
# Excludes ads that only recently started (e.g. spend on 2 days at the end).
MIN_SPEND_DAYS_IN_PERIOD = 5


def _is_install_action(action_type: str) -> bool:
    if not action_type:
        return False
    if action_type in INSTALL_ACTION_TYPES:
        return True
    lowered = action_type.lower()
    return "app_install" in lowered or lowered.endswith(".install")


@dataclass
class CampaignRow:
    name: str
    spend: float
    installs: int
    impressions: int
    reach: int
    cpi_from_meta: float | None = None

    @property
    def cpi(self) -> float | None:
        if self.cpi_from_meta is not None and self.cpi_from_meta > 0:
            return self.cpi_from_meta
        if self.installs <= 0:
            return None
        return self.spend / self.installs


@dataclass
class AdRow:
    ad_id: str
    campaign_name: str
    spend: float
    installs: int
    cpi_from_meta: float | None = None

    @property
    def cpi(self) -> float | None:
        if self.cpi_from_meta is not None and self.cpi_from_meta > 0:
            return self.cpi_from_meta
        if self.installs <= 0:
            return None
        return self.spend / self.installs


def _float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _install_count(actions: list[dict[str, Any]] | None) -> int:
    if not actions:
        return 0
    counts = {
        a.get("action_type", ""): int(float(a.get("value", 0)))
        for a in actions
        if _is_install_action(a.get("action_type", ""))
    }
    if not counts:
        return 0
    for action_type in INSTALL_COUNT_PRIORITY:
        if action_type in counts:
            return counts[action_type]
    return max(counts.values())


def _cpi_from_cost_per_action(
    entries: list[dict[str, Any]] | None,
) -> float | None:
    if not entries:
        return None
    for entry in entries:
        if _is_install_action(entry.get("action_type", "")):
            value = _float(entry.get("value"), default=-1.0)
            if value > 0:
                return value
    return None


def _resolve_install_metrics(
    insight: dict[str, Any], spend: float
) -> tuple[int, float | None]:
    """
    Installs + CPI aligned with Ads Manager "Per Mobile App Install".

    Meta often omits installs from `actions` but provides CPI in
    `cost_per_action_type`. We also check `unique_actions` and derive
    install count from spend ÷ CPI when needed.
    """
    installs = _install_count(insight.get("actions"))
    if installs == 0:
        installs = _install_count(insight.get("unique_actions"))

    cpi = _cpi_from_cost_per_action(insight.get("cost_per_action_type"))

    if installs == 0 and cpi and cpi > 0 and spend > 0:
        installs = max(1, int(round(spend / cpi)))

    if cpi is None and installs > 0 and spend > 0:
        cpi = spend / installs

    return installs, cpi


def yesterday_et(override: date | None = None) -> date:
    if override is not None:
        return override
    tz = ZoneInfo(REPORT_TIMEZONE)
    return (datetime.now(tz).date() - timedelta(days=1))


def _format_report_date(d: date) -> str:
    return d.strftime("%m/%d/%Y")


def _format_money(amount: float, currency: str) -> str:
    symbol = "$" if currency == "USD" else f"{currency} "
    if currency == "USD":
        return f"${amount:,.2f}"
    return f"{symbol}{amount:,.2f}"


def _format_cpi(cpi: float | None, currency: str) -> str:
    if cpi is None:
        return "—"
    return _format_money(cpi, currency)


def _build_rows(insights: list[dict[str, Any]]) -> list[CampaignRow]:
    """Include only campaigns with spend > 0. Installs/clicks may be 0."""
    rows: list[CampaignRow] = []

    for insight in insights:
        spend = _float(insight.get("spend"))
        if spend <= 0:
            continue
        cid = insight.get("campaign_id", "")
        installs, cpi = _resolve_install_metrics(insight, spend)
        rows.append(
            CampaignRow(
                name=insight.get("campaign_name") or cid,
                spend=spend,
                installs=installs,
                impressions=int(_float(insight.get("impressions"))),
                reach=int(_float(insight.get("reach"))),
                cpi_from_meta=cpi,
            )
        )

    def _cpi_sort_key(row: CampaignRow) -> tuple[int, float]:
        # No installs → no CPI; sort those after campaigns with a CPI.
        if row.cpi is None:
            return (1, 0.0)
        return (0, row.cpi)

    return sorted(rows, key=_cpi_sort_key)


def _cpi_from_period_totals(spend: float, installs: int) -> float | None:
    """CPI for a date range: total spend ÷ total installs."""
    if spend <= 0 or installs <= 0:
        return None
    return spend / installs


def _qualifies_high_cpi_alert(
    spend: float, installs: int, cpi: float | None, *, threshold: float
) -> bool:
    if spend <= 0:
        return False
    if installs == 0:
        return spend > threshold
    return cpi is not None and cpi > threshold


def _high_cpi_sort_key(row: AdRow) -> tuple[int, float]:
    # No installs (CPI undefined) — alert first, then highest CPI to lowest.
    if row.cpi is None:
        return (0, -row.spend)
    return (1, -row.cpi)


def _period_dates(start_date: date, end_date: date) -> set[date]:
    dates: set[date] = set()
    current = start_date
    while current <= end_date:
        dates.add(current)
        current += timedelta(days=1)
    return dates


def _insight_day(insight: dict[str, Any]) -> date | None:
    raw = insight.get("date_start") or insight.get("date_stop")
    if not raw:
        return None
    return date.fromisoformat(str(raw))


def _build_high_cpi_ad_rows(
    daily_insights: list[dict[str, Any]],
    *,
    period_start: date,
    period_end: date,
    threshold: float = HIGH_CPI_AD_THRESHOLD,
) -> list[AdRow]:
    required_days = _period_dates(period_start, period_end)
    spend_days: dict[str, set[date]] = {}
    totals: dict[str, dict[str, Any]] = {}

    for insight in daily_insights:
        ad_id = insight.get("ad_id", "")
        day = _insight_day(insight)
        spend = _float(insight.get("spend"))
        if not ad_id or day not in required_days:
            continue

        if ad_id not in totals:
            totals[ad_id] = {
                "campaign_name": insight.get("campaign_name")
                or insight.get("campaign_id", ""),
                "spend": 0.0,
                "installs": 0,
            }
            spend_days[ad_id] = set()

        if spend > 0:
            spend_days[ad_id].add(day)
        installs, _ = _resolve_install_metrics(insight, spend)
        totals[ad_id]["spend"] += spend
        totals[ad_id]["installs"] += installs

    rows: list[AdRow] = []
    for ad_id, data in totals.items():
        days_with_spend = spend_days.get(ad_id, set())
        if len(days_with_spend) < MIN_SPEND_DAYS_IN_PERIOD:
            continue

        spend = float(data["spend"])
        installs = int(data["installs"])
        cpi = _cpi_from_period_totals(spend, installs)
        if not _qualifies_high_cpi_alert(spend, installs, cpi, threshold=threshold):
            continue
        rows.append(
            AdRow(
                ad_id=ad_id,
                campaign_name=data["campaign_name"],
                spend=spend,
                installs=installs,
                cpi_from_meta=cpi,
            )
        )

    return sorted(rows, key=_high_cpi_sort_key)


def _total_row(rows: list[CampaignRow]) -> CampaignRow:
    return CampaignRow(
        name="Total",
        spend=sum(r.spend for r in rows),
        installs=sum(r.installs for r in rows),
        impressions=sum(r.impressions for r in rows),
        reach=sum(r.reach for r in rows),
    )


def _row_cells(row: CampaignRow, currency: str) -> tuple[str, ...]:
    return (
        row.name,
        _format_money(row.spend, currency),
        str(row.installs),
        _format_cpi(row.cpi, currency),
        f"{row.impressions:,}",
        f"{row.reach:,}",
    )


def _table_separator_for_lines(*lines: str) -> str:
    if not lines:
        return ""
    return "-" * max(len(line) for line in lines)


def _format_table(
    rows: list[CampaignRow], currency: str, *, empty_message: str
) -> str:
    headers = (
        "Campaign Name",
        "Amount Spent",
        "Installs",
        "CPI",
        "Impression",
        "Reach",
    )
    col_widths = [len(h) for h in headers]

    table_rows = [*rows, _total_row(rows)] if rows else []
    formatted = [_row_cells(row, currency) for row in table_rows]
    for cells in (headers, *formatted):
        col_widths = [max(w, len(cell)) for w, cell in zip(col_widths, cells)]

    def line(cells: tuple[str, ...]) -> str:
        return "  ".join(
            cell.ljust(col_widths[i]) for i, cell in enumerate(cells)
        )

    header_line = line(headers)
    if not formatted:
        sep = _table_separator_for_lines(header_line)
        return "\n".join([header_line, sep, empty_message])

    if len(formatted) > 1:
        body_lines = [line(cells) for cells in formatted[:-1]]
        total_line = line(formatted[-1])
        sep = _table_separator_for_lines(header_line, *body_lines, total_line)
        return "\n".join([header_line, sep, *body_lines, sep, total_line])

    body_line = line(formatted[0])
    sep = _table_separator_for_lines(header_line, body_line)
    return "\n".join([header_line, sep, body_line])


def _format_alert_table(
    rows: list[AdRow], currency: str, *, empty_message: str
) -> str:
    headers = (
        "Ad ID",
        "Campaign Name",
        "Amount Spent",
        "Installs",
        "CPI",
    )
    col_widths = [len(h) for h in headers]

    formatted = [
        (
            row.ad_id,
            row.campaign_name,
            _format_money(row.spend, currency),
            str(row.installs),
            _format_cpi(row.cpi, currency),
        )
        for row in rows
    ]
    for cells in (headers, *formatted):
        col_widths = [max(w, len(cell)) for w, cell in zip(col_widths, cells)]

    def line(cells: tuple[str, ...]) -> str:
        return "  ".join(
            cell.ljust(col_widths[i]) for i, cell in enumerate(cells)
        )

    header_line = line(headers)
    if not formatted:
        sep = _table_separator_for_lines(header_line)
        return "\n".join([header_line, sep, empty_message])

    body_lines = [line(cells) for cells in formatted]
    sep = _table_separator_for_lines(header_line, *body_lines)
    return "\n".join([header_line, sep, *body_lines])


def build_daily_report_message(
    report_date: date,
    rows: list[CampaignRow],
    currency: str,
    *,
    high_cpi_rows: list[AdRow] | None = None,
) -> str:
    header = "KOTC Meta App Install Campaign Daily Report"
    date_line = f"Date: {_format_report_date(report_date)}"
    table = _format_table(
        rows,
        currency,
        empty_message="(No app promotion campaigns with spend on this date)",
    )
    parts = [header, date_line, "", f"```\n{table}\n```"]

    if high_cpi_rows is not None:
        ad_table = _format_alert_table(
            high_cpi_rows,
            currency,
            empty_message="(None)",
        )
        parts.extend(
            [
                "",
                (
                    f"⚠️ Attention - The following ads have a CPI > "
                    f"${HIGH_CPI_AD_THRESHOLD:.0f} over the past 7 days"
                ),
                "",
                f"```\n{ad_table}\n```",
            ]
        )

    return "\n".join(parts)


def build_weekly_report_message(
    start_date: date,
    end_date: date,
    rows: list[CampaignRow],
    currency: str,
) -> str:
    header = "KOTC Meta App Install Campaign Weekly Report"
    date_line = (
        f"Date: {_format_report_date(start_date)}-"
        f"{_format_report_date(end_date)}"
    )
    table = _format_table(
        rows,
        currency,
        empty_message="(No app promotion campaigns with spend in this period)",
    )
    return f"{header}\n{date_line}\n\n```\n{table}\n```"


def past_week_range_et(week_end_override: date | None = None) -> tuple[date, date]:
    """
    Seven-day window ending yesterday (ET).

    Example: report runs Friday 2026-06-05 → 2026-05-29 through 2026-06-04.
    """
    if week_end_override is not None:
        end = week_end_override
    else:
        end = yesterday_et()
    start = end - timedelta(days=6)
    return start, end


def run() -> int:
    try:
        cfg = Config.from_env()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    report_date = yesterday_et(cfg.report_date_override)
    meta = MetaClient(cfg.meta_access_token, cfg.meta_ad_account_id)
    slack = SlackNotifier(cfg.slack_webhook_url)

    insights = meta.app_promotion_insights_for_date(
        report_date,
        cfg.campaign_objective,
        campaign_ids=cfg.campaign_ids,
    )
    period_start, period_end = past_week_range_et(cfg.report_date_override)
    ad_daily_insights = meta.app_promotion_ad_insights_for_range(
        period_start,
        period_end,
        cfg.campaign_objective,
        campaign_ids=cfg.campaign_ids,
        daily=True,
    )
    currency = meta.account_currency()

    rows = _build_rows(insights)
    high_cpi_rows = _build_high_cpi_ad_rows(
        ad_daily_insights,
        period_start=period_start,
        period_end=period_end,
    )
    message = build_daily_report_message(
        report_date,
        rows,
        currency,
        high_cpi_rows=high_cpi_rows,
    )

    slack.send(
        f"KOTC Meta App Install Campaign Daily Report — {_format_report_date(report_date)}",
        text=message,
    )
    print(
        f"Posted daily report for {report_date.isoformat()} "
        f"({len(rows)} campaign(s), {len(high_cpi_rows)} ad(s) with 7-day CPI > "
        f"${HIGH_CPI_AD_THRESHOLD:.0f})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
