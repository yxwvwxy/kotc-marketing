#!/usr/bin/env python3
"""Headed login + post-login Overview CSV export in one browser session.

Usage:
  ./scripts/test_login.sh
  # or with lookback days:
  LOOKBACK_DAYS=7 ./scripts/test_login.sh
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

from src.branch_browser_export import AUTH_STATE_PATH, DOWNLOAD_DIR, BranchBrowserExporter


def main() -> None:
    email = os.environ.get("BRANCH_EMAIL", "").strip()
    password = os.environ.get("BRANCH_PASSWORD", "").strip()
    if not email or not password:
        raise SystemExit("Set BRANCH_EMAIL and BRANCH_PASSWORD in .env first.")

    tz_name = os.environ.get("SYNC_TIMEZONE", "America/New_York")
    lookback = int(os.environ.get("LOOKBACK_DAYS", "7"))
    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()
    end = today - timedelta(days=1)
    start = end - timedelta(days=lookback - 1)

    summary_url = os.environ.get("BRANCH_SUMMARY_URL", "").strip()
    print("Opening headed browser: login → Overview export ...")
    print(f"Sync window: {start} -> {end} (tz={tz_name})")
    print("Watch: Work email → Continue → Password → Continue → Dashboard → CSV")

    exporter = BranchBrowserExporter(
        email,
        password,
        summary_url=summary_url,
        headed=True,
        timeout_ms=120_000,
        timezone=tz_name,
    )

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = DOWNLOAD_DIR / f"summary-table-export_{start}_{end}_{stamp}.csv"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=400)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(120_000)

        try:
            exporter._login(page)
            context.storage_state(path=str(AUTH_STATE_PATH))
            print(f"Saved session: {AUTH_STATE_PATH}")
            shot = DOWNLOAD_DIR / "branch_login_success.png"
            page.screenshot(path=str(shot), full_page=True)
            print(f"Login OK. URL={page.url}")
            print(f"Screenshot: {shot}")

            print("Continuing post-login scrape (Overview → download) ...")
            exporter._run_export_after_login(page, start, end, out_path)
            exporter._validate_export(out_path)
            print(f"Downloaded Branch CSV: {out_path} ({out_path.stat().st_size} bytes)")

            print("Browser will stay open 15 seconds so you can inspect ...")
            time.sleep(15)
        except Exception as exc:
            shot = DOWNLOAD_DIR / "branch_login_failed.png"
            try:
                page.screenshot(path=str(shot), full_page=True)
                print(f"Failure screenshot: {shot}")
            except Exception:
                pass
            print(f"Login/export test failed: {exc}")
            print("Browser will stay open 60 seconds so you can inspect ...")
            time.sleep(60)
            raise
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
