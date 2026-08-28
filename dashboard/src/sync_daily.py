#!/usr/bin/env python3
"""Daily Branch → BigQuery sync via browser CSV export.

Default flow:
  Playwright login → download Summary CSV → convert → DELETE date range → LOAD

Usage:
  export BRANCH_EMAIL=...
  export BRANCH_PASSWORD=...
  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json
  python -m src.sync_daily

  python -m src.sync_daily --dry-run
  python -m src.sync_daily --from-csv ~/Downloads/summary-table-export.csv
  python -m src.sync_daily --lookback-days 7
"""

from __future__ import annotations

import argparse
import importlib.util
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def _load_convert_module():
    path = ROOT / "bigquery" / "convert_branch_export.py"
    spec = importlib.util.spec_from_file_location("convert_branch_export", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load converter at {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


from src.branch_browser_export import BranchBrowserExporter
from src.config import Settings


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sync Branch summary metrics into BigQuery")
    p.add_argument("--lookback-days", type=int, default=None)
    p.add_argument("--start", type=str, default=None, help="YYYY-MM-DD inclusive")
    p.add_argument("--end", type=str, default=None, help="YYYY-MM-DD inclusive")
    p.add_argument("--dry-run", action="store_true", help="Download+convert only; do not write BQ")
    p.add_argument(
        "--from-csv",
        type=str,
        default=None,
        help="Skip browser download; use an existing Branch summary CSV/Excel",
    )
    p.add_argument(
        "--headed",
        action="store_true",
        help="Show browser window (overrides BRANCH_HEADED)",
    )
    return p.parse_args()


def resolve_window(args: argparse.Namespace, settings: Settings) -> tuple[date, date]:
    tz = ZoneInfo(settings.timezone)
    today = datetime.now(tz).date()
    if args.start and args.end:
        return date.fromisoformat(args.start), date.fromisoformat(args.end)
    lookback = args.lookback_days or settings.lookback_days
    end = today - timedelta(days=1)
    start = end - timedelta(days=lookback - 1)
    return start, end


def main() -> None:
    args = parse_args()
    settings = Settings.from_env(require_branch_login=not bool(args.from_csv))
    start, end = resolve_window(args, settings)
    print(f"Sync window: {start} -> {end} (tz={settings.timezone})")

    if args.from_csv:
        raw_csv = Path(args.from_csv).expanduser().resolve()
        if not raw_csv.exists():
            raise SystemExit(f"CSV not found: {raw_csv}")
        print(f"Using local file: {raw_csv}")
    else:
        exporter = BranchBrowserExporter(
            settings.branch_email,
            settings.branch_password,
            summary_url=settings.branch_summary_url,
            headed=args.headed or settings.branch_headed,
            timezone=settings.timezone,
        )
        raw_csv = exporter.export_summary_csv(start, end)

    convert_mod = _load_convert_module()
    rows, skipped = convert_mod.convert_to_rows(raw_csv)
    upload_csv = convert_mod.convert(raw_csv)
    print(f"Converted rows: {len(rows)} (skipped {skipped})")
    print(f"Upload CSV: {upload_csv}")
    if rows:
        print("Sample row:", rows[0])

    if args.dry_run:
        print("Dry run complete — BigQuery not modified.")
        return

    from src.bigquery_loader import BigQueryLoader

    # Only load rows inside the sync window (export may include extra days)
    window_rows = [r for r in rows if start.isoformat() <= r["date"] <= end.isoformat()]
    print(f"Rows in sync window: {len(window_rows)}")
    loader = BigQueryLoader(settings.table_id)
    n = loader.replace_date_range(window_rows, start, end)
    print(f"Done. Wrote {n} rows to {settings.table_id}")


if __name__ == "__main__":
    main()
