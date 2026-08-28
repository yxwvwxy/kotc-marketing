#!/usr/bin/env python3
"""Weekly Slack report for OUTCOME_APP_PROMOTION campaigns (past 7 days, US/Eastern)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Config
from meta_client import MetaClient
from monitor import (
    _build_rows,
    _format_report_date,
    build_weekly_report_message,
    past_week_range_et,
)
from slack_notifier import SlackNotifier


def run() -> int:
    try:
        cfg = Config.from_env()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    start_date, end_date = past_week_range_et(cfg.report_week_end_override)
    meta = MetaClient(cfg.meta_access_token, cfg.meta_ad_account_id)
    slack = SlackNotifier(cfg.slack_webhook_url)

    insights = meta.app_promotion_insights_for_range(
        start_date,
        end_date,
        cfg.campaign_objective,
        campaign_ids=cfg.campaign_ids,
    )
    currency = meta.account_currency()

    rows = _build_rows(insights)
    message = build_weekly_report_message(start_date, end_date, rows, currency)

    slack.send(
        "KOTC Meta App Install Campaign Weekly Report — "
        f"{_format_report_date(start_date)}-{_format_report_date(end_date)}",
        text=message,
    )
    print(
        f"Posted weekly report for {start_date.isoformat()} to "
        f"{end_date.isoformat()} ({len(rows)} campaign(s))."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
