#!/usr/bin/env python3
"""Print weekly app-promotion report to the terminal (no Slack)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import Config
from meta_client import MetaClient
from monitor import _build_rows, build_weekly_report_message, past_week_range_et


def main() -> int:
    cfg = Config.from_env()
    start_date, end_date = past_week_range_et(cfg.report_week_end_override)
    meta = MetaClient(cfg.meta_access_token, cfg.meta_ad_account_id)

    insights = meta.app_promotion_insights_for_range(
        start_date,
        end_date,
        cfg.campaign_objective,
        campaign_ids=cfg.campaign_ids,
    )
    currency = meta.account_currency()
    rows = _build_rows(insights)
    print(build_weekly_report_message(start_date, end_date, rows, currency))
    print(
        f"\n({len(rows)} campaign(s) with spend > 0)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
