#!/usr/bin/env python3
"""Branch Dashboard → BigQuery loader.

Pulls the same 7-day Summary export the Looker table uses, converts it, then
replaces those dates in:

  kotc-dashboard-auto-update.branch.daily_campaign_metrics

Paired with KOTC Meta Monitor `src/meta_to_bigquery.py`, which writes Meta
spend/CPI into `kotc-dashboard-auto-update.meta.daily_campaign_metrics`.
Join view (not applied): `bigquery/views/meta_branch_campaign_daily.sql`.

Standalone — not scheduled. Inbox drag-and-drop is what writes BigQuery locally.

Leave EXECUTE_LOAD as False so this never queries Branch or writes BigQuery.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXECUTE_LOAD = False

DEFAULT_PROJECT = "kotc-dashboard-auto-update"
DEFAULT_DATASET = "branch"
DEFAULT_TABLE = "daily_campaign_metrics"
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_TIMEZONE = "America/New_York"


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def sync_window() -> tuple[date, date]:
    tz = ZoneInfo(os.environ.get("SYNC_TIMEZONE", DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE)
    lookback = int(os.environ.get("SYNC_LOOKBACK_DAYS", str(DEFAULT_LOOKBACK_DAYS)) or DEFAULT_LOOKBACK_DAYS)
    end = datetime.now(tz).date() - timedelta(days=1)
    start = end - timedelta(days=lookback - 1)
    return start, end


def table_id() -> str:
    project = os.environ.get("BQ_PROJECT_ID", DEFAULT_PROJECT).strip() or DEFAULT_PROJECT
    dataset = os.environ.get("BQ_DATASET", DEFAULT_DATASET).strip() or DEFAULT_DATASET
    table = os.environ.get("BQ_TABLE", DEFAULT_TABLE).strip() or DEFAULT_TABLE
    return f"{project}.{dataset}.{table}"


def load_branch_rows(start: date, end: date) -> list[dict]:
    from src.branch_browser_export import BranchBrowserExporter
    from src.config import Settings
    from src.sync_daily import _load_convert_module

    settings = Settings.from_env(require_branch_login=True)
    exporter = BranchBrowserExporter(
        settings.branch_email,
        settings.branch_password,
        summary_url=settings.branch_summary_url,
        headed=settings.branch_headed,
        timezone=settings.timezone,
    )
    raw_csv = exporter.export_summary_csv(start, end)
    convert_mod = _load_convert_module()
    rows, skipped = convert_mod.convert_to_rows(raw_csv)
    print(f"Converted rows: {len(rows)} (skipped {skipped})")
    return [
        row
        for row in rows
        if start.isoformat() <= row["date"] <= end.isoformat()
    ]


def write_bigquery(rows: list[dict], start: date, end: date) -> int:
    from src.bigquery_loader import BigQueryLoader

    loader = BigQueryLoader(table_id())
    return loader.replace_date_range(rows, start, end)


def run() -> int:
    _load_dotenv()
    start, end = sync_window()
    target = table_id()
    print(f"Branch → BigQuery  {start} -> {end}")
    print(f"Table: {target}")

    if not EXECUTE_LOAD:
        print("EXECUTE_LOAD is False — Branch was not queried and BigQuery was not modified.")
        return 0

    rows = load_branch_rows(start, end)
    print(f"Rows in sync window: {len(rows)}")
    if rows:
        print("Sample row:", rows[0])
    n = write_bigquery(rows, start, end)
    print(f"Wrote {n} rows to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
