#!/usr/bin/env python3
"""Print yesterday's app-promotion report to the terminal (no Slack)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import Config
from meta_client import MetaClient
from monitor import (
    _build_high_cpi_ad_rows,
    _build_rows,
    build_daily_report_message,
    past_week_range_et,
    yesterday_et,
)


def main() -> int:
    cfg = Config.from_env()
    report_date = yesterday_et(cfg.report_date_override)
    meta = MetaClient(cfg.meta_access_token, cfg.meta_ad_account_id)

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
    print(
        build_daily_report_message(
            report_date,
            rows,
            currency,
            high_cpi_rows=high_cpi_rows,
        )
    )
    print(
        f"\n({len(rows)} campaign(s) with spend > 0, "
        f"{len(high_cpi_rows)} ad(s) with 7-day CPI > $8)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
