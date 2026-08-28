"""Download Branch Analysis Overview CSV via Playwright.

Target UI (from user screen recording 2026-08-10):
  App: MCAT: King of the curve
  Nav: ANALYSIS → Overview
  Date range: explicit start/end ending yesterday (NOT "Last 7 days", which includes today)
    e.g. on 8/10 use 8/03 → 8/09
  Compare by: date, ad partner, campaign, platform, ad partner (3p)
  Unique: ON, Organic: OFF, interval: Day
  Columns: open header columns icon → ensure Selected Columns complete
  Export: download icon to the right of the Day dropdown (table toolbar)
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_DIR = ROOT / "bigquery" / "data"
AUTH_STATE_PATH = DOWNLOAD_DIR / "branch_auth_state.json"

LOGIN_URL = "https://app.branch.io/signin"
APP_NAME = "MCAT: King of the curve"

# Columns that must be present in the exported CSV (Branch names).
EXPECTED_EXPORT_COLUMNS = [
    "date",
    "ad partner",
    "campaign",
    "platform",
    "ad partner (3p)",
    "clicks",
    "installs",
    "REGISTER",
    "COMPLETE_REGISTRATION",
    "INITIATE_PURCHASE",
    "PURCHASE",
    "cost",
    "revenue",
    "eCPI",
    "eCPC",
    "rc_trial_cancelled_event",
    "rc_expiration_event",
    "rc_cancellation_event",
    "rc_trial_started_event",
    "rc_product_change_event",
]

COMPARE_BY = [
    "date",
    "ad partner",
    "campaign",
    "platform",
    "ad partner (3p)",
]

# Names as shown in Customize Columns → Event/Metric lists
SELECTED_METRIC_COLUMNS = [
    "clicks",
    "installs",
    "REGISTER",
    "COMPLETE_REGISTRATION",
    "INITIATE_PURCHASE",
    "PURCHASE",
    "cost",
    "revenue",
    "eCPI",
    "eCPC",
    "rc_trial_cancelled_event",
    "rc_expiration_event",
    "rc_cancellation_event",
    "rc_trial_started_event",
    "rc_product_change_event",
]


class BranchBrowserExporter:
    def __init__(
        self,
        email: str,
        password: str,
        *,
        summary_url: str = "",
        headed: bool = False,
        timezone: str = "America/New_York",
        timeout_ms: int = 90_000,
        app_name: str = APP_NAME,
    ):
        self.email = email
        self.password = password
        self.summary_url = summary_url.strip()
        self.headed = headed
        self.tz = ZoneInfo(timezone)
        self.timeout_ms = timeout_ms
        self.app_name = app_name

    def export_summary_csv(self, start: date, end: date) -> Path:
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = DOWNLOAD_DIR / f"summary-table-export_{start}_{end}_{stamp}.csv"

        with sync_playwright() as p:
            # Match successful headed login tests: slow_mo=400 helps Auth0 register input.
            browser = p.chromium.launch(
                headless=not self.headed,
                slow_mo=400 if self.headed else 0,
            )
            context_kwargs = {"accept_downloads": True}
            if AUTH_STATE_PATH.exists():
                print(f"Reusing saved login session: {AUTH_STATE_PATH}")
                context_kwargs["storage_state"] = str(AUTH_STATE_PATH)
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            page.set_default_timeout(self.timeout_ms)

            try:
                if AUTH_STATE_PATH.exists():
                    page.goto("https://dashboard.branch.io/", wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)
                    if self._needs_login(page):
                        print("Saved session expired; logging in again ...")
                        self._login(page)
                        context.storage_state(path=str(AUTH_STATE_PATH))
                else:
                    self._login(page)
                    context.storage_state(path=str(AUTH_STATE_PATH))
                    print(f"Saved login session to {AUTH_STATE_PATH}")

                self._run_export_after_login(page, start, end, out_path)
            finally:
                context.close()
                browser.close()

        if not out_path.exists() or out_path.stat().st_size < 20:
            raise RuntimeError(f"Download failed or empty file: {out_path}")
        self._validate_export(out_path)
        print(f"Downloaded Branch CSV: {out_path} ({out_path.stat().st_size} bytes)")
        return out_path

    def _run_export_after_login(self, page, start: date, end: date, out_path: Path) -> None:
        """Post-login scrape: app → Overview → configure → download CSV."""
        self._select_app(page)
        self._open_overview(page)
        self._configure_report(page, start, end)
        self._download_csv(page, out_path)

    def _needs_login(self, page) -> bool:
        u = page.url.lower()
        if "signin" in u or "auth0.branch.io" in u or "/login" in u:
            return True
        try:
            if page.locator('input[name="email"]').count() and page.locator('input[name="email"]').first.is_visible():
                return True
        except Exception:
            pass
        return False

    def _login(self, page) -> None:
        """Branch uses a 2-step signin on app.branch.io: Work email → Continue → password."""
        print("Logging into Branch (app.branch.io/signin) ...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        for label in ("Accept", "Accept all", "I agree", "Got it"):
            try:
                btn = page.get_by_role("button", name=re.compile(label, re.I))
                if btn.count() and btn.first.is_visible():
                    btn.first.click(timeout=2000)
            except Exception:
                pass

        # Step 1: Work email (input type=text name=email — NOT type=email)
        email_box = None
        for selector in (
            'input[name="email"]',
            'input[type="text"]',
            'input[type="email"]',
            'input[autocomplete="username"]',
        ):
            loc = page.locator(selector)
            try:
                loc.first.wait_for(state="visible", timeout=10_000)
                email_box = loc.first
                break
            except Exception:
                continue
        if email_box is None:
            # labeled "Work email"
            try:
                email_box = page.get_by_label(re.compile(r"work email|email", re.I))
                email_box.wait_for(state="visible", timeout=5_000)
            except Exception as exc:
                shot = DOWNLOAD_DIR / "branch_login_debug.png"
                try:
                    page.screenshot(path=str(shot), full_page=True)
                except Exception:
                    pass
                raise RuntimeError(
                    f"Could not find Work email field. URL={page.url}. "
                    f"Screenshot: {shot}. Set BRANCH_HEADED=1 to inspect."
                ) from exc

        email_box.fill(self.email)
        print("Filled work email; clicking Continue ...")
        try:
            page.get_by_role("button", name=re.compile(r"^Continue$", re.I)).first.click(timeout=5000)
        except Exception:
            email_box.press("Enter")

        # Step 2: Auth0 password page (auth0.branch.io/u/login/password)
        try:
            page.wait_for_url(re.compile(r"auth0\.branch\.io|password"), timeout=30_000)
        except PlaywrightTimeoutError:
            pass
        print(f"Password step URL: {page.url}")

        password_box = None
        for selector in (
            'input#password',
            'input[name="password"]',
            'input[type="password"]',
        ):
            loc = page.locator(selector)
            try:
                loc.first.wait_for(state="visible", timeout=20_000)
                password_box = loc.first
                break
            except Exception:
                continue
        if password_box is None:
            raise RuntimeError(
                "Password field did not appear after Continue. "
                f"URL={page.url}. Set BRANCH_HEADED=1."
            )

        # Auth0 React inputs: click + type so the field actually receives keystrokes
        password_box.click()
        password_box.fill("")
        password_box.press_sequentially(self.password, delay=25)
        print("Filled password.")

        captcha = self._auth0_has_captcha(page)
        if captcha:
            print(
                "\n*** Auth0 showed reCAPTCHA ***\n"
                "In the browser window: check \"I'm not a robot\", solve if asked,\n"
                "then click Continue. Waiting up to 3 minutes...\n"
            )
            if not self.headed:
                raise RuntimeError(
                    "Auth0 reCAPTCHA blocks headless login. "
                    "Run with BRANCH_HEADED=1 (or ./scripts/test_login.sh), "
                    "complete the captcha once; session is saved for reuse."
                )
            # Do not auto-click Continue — user must complete captcha first.
            self._wait_left_auth0(page, timeout_ms=180_000, allow_manual=True)
        else:
            print("Submitting Auth0 Continue ...")
            submit = page.locator(
                'button[type="submit"][name="action"], button[type="submit"]'
            )
            try:
                with page.expect_navigation(
                    timeout=self.timeout_ms, wait_until="domcontentloaded"
                ):
                    if submit.count():
                        submit.first.click()
                    else:
                        page.get_by_role(
                            "button", name=re.compile(r"^Continue$", re.I)
                        ).first.click()
            except PlaywrightTimeoutError:
                try:
                    if submit.count():
                        submit.first.click()
                    password_box.press("Enter")
                except Exception:
                    pass
            # If captcha appears after submit, fall back to manual wait
            if self._still_on_auth0(page) and self._auth0_has_captcha(page):
                print(
                    "\n*** Auth0 reCAPTCHA appeared after submit ***\n"
                    "Complete captcha + Continue in the browser (3 min)...\n"
                )
                if not self.headed:
                    raise RuntimeError(
                        "Auth0 reCAPTCHA after submit. Re-run with BRANCH_HEADED=1."
                    )
                self._wait_left_auth0(page, timeout_ms=180_000, allow_manual=True)
            else:
                self._wait_left_auth0(page, timeout_ms=60_000, allow_manual=False)

        page.wait_for_timeout(2500)
        if "app.branch.io" in page.url and "dashboard.branch.io" not in page.url:
            try:
                page.goto("https://dashboard.branch.io/", wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
            except Exception:
                pass
        print(f"Logged in. Current URL: {page.url}")

    def _auth0_has_captcha(self, page) -> bool:
        try:
            if page.locator('iframe[src*="recaptcha"], iframe[title*="reCAPTCHA" i]').count():
                return True
            if page.locator("text=/I.m not a robot|reCAPTCHA/i").count():
                return True
        except Exception:
            pass
        return False

    def _still_on_auth0(self, page) -> bool:
        u = (page.url or "").lower()
        return "auth0.branch.io" in u or "/signin" in u

    def _wait_left_auth0(self, page, *, timeout_ms: int, allow_manual: bool) -> None:
        """Success = leave Auth0 / signin. Do not treat auth0 password URL as success."""
        try:
            page.wait_for_function(
                """() => {
                    const u = location.href;
                    if (u.includes('auth0.branch.io')) return false;
                    if (u.includes('/signin')) return false;
                    return u.includes('dashboard.branch.io') || u.includes('app.branch.io');
                }""",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError as exc:
            shot = DOWNLOAD_DIR / "branch_login_failed.png"
            try:
                page.screenshot(path=str(shot), full_page=True)
            except Exception:
                pass
            body = ""
            try:
                body = page.locator("body").inner_text(timeout=3000)[:800]
            except Exception:
                pass
            hint = (
                "Complete reCAPTCHA in the headed browser, or check BRANCH_PASSWORD."
                if allow_manual
                else "Wrong password, or Auth0 blocked automation (reCAPTCHA). "
                "Run ./scripts/test_login.sh headed and complete captcha once."
            )
            raise RuntimeError(
                f"Login did not leave Auth0. {hint}\n"
                f"URL={page.url}\nPage text: {body}\nScreenshot: {shot}"
            ) from exc

    def _select_app(self, page) -> None:
        """Ensure app dropdown is MCAT: King of the curve."""
        print(f"Selecting app: {self.app_name}")
        try:
            # App switcher near top of sidebar
            switcher = page.get_by_text(re.compile(r"MCAT|King of the curve", re.I)).first
            if switcher.count() and self.app_name.lower() in (switcher.inner_text() or "").lower():
                print("App already selected.")
                return
        except Exception:
            pass

        for sel in (
            page.get_by_role("button", name=re.compile(r"MCAT|King of the curve|select app", re.I)),
            page.locator('[data-testid*="app" i]'),
            page.locator("aside >> role=button").first,
        ):
            try:
                if hasattr(sel, "count") and sel.count() == 0:
                    continue
                sel.click(timeout=3000)
                page.get_by_text(self.app_name, exact=False).first.click(timeout=5000)
                page.wait_for_timeout(2000)
                print("App selected.")
                return
            except Exception:
                continue
        print("Warning: could not confirm app switcher; continuing with current app.")

    def _open_overview(self, page) -> None:
        if self.summary_url:
            print("Opening BRANCH_SUMMARY_URL ...")
            page.goto(self.summary_url, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            return

        print("Opening ANALYSIS → Overview ...")
        # Sidebar: ANALYSIS / Overview (from recording)
        try:
            page.get_by_role("link", name=re.compile(r"^Overview$", re.I)).first.click(timeout=5000)
            page.wait_for_timeout(2500)
        except Exception:
            try:
                page.get_by_text(re.compile(r"^Overview$", re.I)).first.click(timeout=5000)
                page.wait_for_timeout(2500)
            except Exception as exc:
                raise RuntimeError(
                    "Could not open ANALYSIS → Overview. "
                    "Copy that page URL into BRANCH_SUMMARY_URL."
                ) from exc

        if not self._page_looks_like_overview(page):
            # try direct paths used by Branch analysis
            for url in (
                "https://dashboard.branch.io/analysis/overview",
                "https://dashboard.branch.io/overview",
            ):
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    page.wait_for_timeout(2500)
                    if self._page_looks_like_overview(page):
                        break
                except Exception:
                    continue

        if not self._page_looks_like_overview(page):
            raise RuntimeError(
                f"Not on Analysis Overview after navigation. URL={page.url}. "
                "Set BRANCH_SUMMARY_URL to your Overview page."
            )
        print(f"Overview ready: {page.url}")

    def _page_looks_like_overview(self, page) -> bool:
        try:
            text = page.content().lower()
        except Exception:
            return False
        markers = ("compare by", "unique", "organic", "installs", "day")
        return sum(1 for m in markers if m in text) >= 3

    def _configure_report(self, page, start: date, end: date) -> None:
        """Set explicit dates (exclude today), Unique/Day, compare-by, columns."""
        print("Configuring report controls ...")
        # Do NOT use "Last 7 days" — Branch includes today. Use start→end (= yesterday).
        self._set_explicit_date_range(page, start, end)

        self._set_checkbox(page, "Unique", checked=True)
        self._set_checkbox(page, "Organic", checked=False)

        try:
            day = page.get_by_role("button", name=re.compile(r"^Day$", re.I))
            if day.count() and day.first.is_visible():
                print("Interval already Day")
            else:
                interval = page.get_by_role("button", name=re.compile(r"Week|Month|Day", re.I))
                if interval.count():
                    interval.first.click(timeout=3000)
                    page.get_by_role("option", name=re.compile(r"^Day$", re.I)).first.click(timeout=3000)
                    page.wait_for_timeout(1000)
        except Exception:
            print("Warning: could not confirm Day interval")

        self._ensure_compare_by(page)
        self._ensure_selected_columns(page)
        page.wait_for_timeout(2000)

    def _set_explicit_date_range(self, page, start: date, end: date) -> None:
        """Set DATE RANGE inputs to start/end (MM/DD). Prefer Custom over Last 7 days."""
        start_s = start.strftime("%m/%d")
        end_s = end.strftime("%m/%d")
        print(f"Setting explicit date range {start_s} -> {end_s} (exclude today) ...")

        # Switch preset away from Last 7 days if needed
        try:
            preset = page.get_by_role("button", name=re.compile(r"Last 7 days|Custom", re.I))
            if preset.count():
                label = (preset.first.inner_text() or "").lower()
                if "last 7" in label:
                    preset.first.click(timeout=3000)
                    # Pick Custom if available, else just edit the boxes
                    try:
                        page.get_by_text(re.compile(r"^Custom", re.I)).first.click(timeout=3000)
                    except Exception:
                        page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
        except Exception:
            pass

        filled = False
        try:
            region = page.get_by_text(re.compile(r"DATE RANGE", re.I)).locator("xpath=ancestor::*[1]")
            boxes = region.locator("input")
            if boxes.count() >= 2:
                boxes.nth(0).click()
                boxes.nth(0).fill("")
                boxes.nth(0).fill(start_s)
                boxes.nth(1).click()
                boxes.nth(1).fill("")
                boxes.nth(1).fill(end_s)
                page.keyboard.press("Enter")
                page.wait_for_timeout(2000)
                filled = True
        except Exception:
            pass

        if not filled:
            # Broader search for two date-like inputs near the top bar
            try:
                boxes = page.locator('input[value*="/"], input[placeholder*="/"]')
                if boxes.count() >= 2:
                    boxes.nth(0).fill(start_s)
                    boxes.nth(1).fill(end_s)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(2000)
                    filled = True
            except Exception:
                pass

        if not filled:
            raise RuntimeError(
                f"Could not set date range to {start_s}-{end_s}. "
                "Set BRANCH_HEADED=1 and check DATE RANGE inputs."
            )
        print(f"Date range set to {start_s} → {end_s}")

    def _ensure_compare_by(self, page) -> None:
        """Ensure compare-by chips match screenshot; add missing from dropdown."""
        print("Ensuring Compare by dimensions ...")
        body = ""
        try:
            # Scope to compare-by row if possible
            row = page.get_by_text(re.compile(r"^Compare by$", re.I)).locator(
                "xpath=ancestor::*[1]"
            )
            body = (row.inner_text(timeout=3000) or "").lower()
        except Exception:
            try:
                body = (page.locator("body").inner_text(timeout=5000) or "").lower()
            except Exception:
                body = ""

        missing = [d for d in COMPARE_BY if d.lower() not in body]
        if not missing:
            print("Compare by already complete.")
            return

        print(f"Compare by missing: {missing} — opening dropdown")
        try:
            # Arrow inside Compare by control
            compare = page.get_by_text(re.compile(r"^Compare by$", re.I)).locator(
                "xpath=following::*[1]"
            )
            arrow = page.locator(
                'text=Compare by >> xpath=following::*[contains(@class,"arrow") or self::button or self::svg][1]'
            )
            opened = False
            for target in (
                page.get_by_text(re.compile(r"^Compare by$", re.I)),
                compare,
                arrow,
            ):
                try:
                    target.first.click(timeout=3000)
                    opened = True
                    break
                except Exception:
                    continue
            if not opened:
                raise RuntimeError("Could not open Compare by dropdown")

            page.wait_for_timeout(800)
            for dim in missing:
                # date is usually fixed; still try
                try:
                    opt = page.get_by_text(re.compile(rf"^{re.escape(dim)}$", re.I))
                    if opt.count():
                        opt.first.click(timeout=3000)
                        page.wait_for_timeout(400)
                        print(f"  added compare-by: {dim}")
                except Exception as exc:
                    print(f"  warn: could not add compare-by {dim}: {exc}")
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
        except Exception as exc:
            print(f"Warning: Compare by setup incomplete: {exc}")

    def _ensure_selected_columns(self, page) -> None:
        """Open columns icon (table header right) and add any missing Selected Columns."""
        print("Checking Customize Columns / Selected Columns ...")
        opened = False
        candidates = [
            page.locator('[aria-label*="column" i]'),
            page.locator('[aria-label*="Customize" i]'),
            page.locator('[title*="column" i]'),
            page.locator('[data-testid*="column" i]'),
            # three vertical bars icon near table header right
            page.locator('button:near(:text("Day"))').last,
            page.get_by_role("button", name=re.compile(r"column|customize", re.I)),
        ]
        for cand in candidates:
            try:
                if not cand.count():
                    continue
                loc = cand.first
                if not loc.is_visible():
                    continue
                loc.click(timeout=3000)
                page.wait_for_timeout(1000)
                if page.get_by_text(re.compile(r"Customize Columns|Selected Columns", re.I)).count():
                    opened = True
                    break
                page.keyboard.press("Escape")
            except Exception:
                continue

        if not opened:
            # Last resort: click last icon buttons in the table toolbar row
            try:
                toolbar = page.get_by_text(re.compile(r"^Unique$", re.I)).locator(
                    "xpath=ancestor::div[3]"
                )
                icons = toolbar.locator("button")
                for i in range(icons.count() - 1, -1, -1):
                    try:
                        icons.nth(i).click(timeout=2000)
                        page.wait_for_timeout(800)
                        if page.get_by_text(re.compile(r"Customize Columns|Selected Columns", re.I)).count():
                            opened = True
                            break
                        page.keyboard.press("Escape")
                    except Exception:
                        continue
            except Exception:
                pass

        if not opened:
            print(
                "Warning: could not open Customize Columns modal "
                "(three-bar icon on table header right). "
                "Assuming saved column set is already correct."
            )
            return

        # Read Selected Columns panel text
        selected_text = ""
        try:
            selected_panel = page.get_by_text(re.compile(r"^Selected Columns$", re.I)).locator(
                "xpath=ancestor::*[contains(@class,'column') or self::div][1]"
            )
            selected_text = (selected_panel.inner_text(timeout=3000) or "").lower()
        except Exception:
            try:
                selected_text = (page.get_by_text(re.compile(r"Selected Columns", re.I))
                                 .locator("xpath=following::div[1]")
                                 .inner_text(timeout=3000) or "").lower()
            except Exception:
                selected_text = (page.locator("body").inner_text(timeout=3000) or "").lower()

        missing = [c for c in SELECTED_METRIC_COLUMNS if c.lower() not in selected_text]
        if not missing:
            print("Selected Columns already complete.")
            page.get_by_role("button", name=re.compile(r"^Apply$", re.I)).first.click(timeout=3000)
            page.wait_for_timeout(1500)
            return

        print(f"Selected Columns missing: {missing} — adding from Event/Metric lists")
        for col in missing:
            added = False
            # Search box in Event Columns / Metric Columns
            for search_label in ("Search Event", "Search Metric", "Search"):
                try:
                    search = page.get_by_placeholder(re.compile(search_label, re.I))
                    if search.count() == 0:
                        continue
                    search.first.fill("")
                    search.first.fill(col)
                    page.wait_for_timeout(500)
                    # Click + next to the matching row
                    row = page.get_by_text(re.compile(rf"^{re.escape(col)}$", re.I))
                    if row.count():
                        item = row.first.locator("xpath=ancestor::li[1]|ancestor::div[contains(@class,'item') or contains(@class,'row')][1]")
                        plus = item.locator("button, [role='button']").first
                        if plus.count():
                            plus.click(timeout=2000)
                        else:
                            row.first.locator("xpath=preceding::button[1] | following::button[1]").first.click(
                                timeout=2000
                            )
                        added = True
                        print(f"  added column: {col}")
                        page.wait_for_timeout(400)
                        break
                except Exception:
                    continue
            if not added:
                # Try visible + buttons next to exact label without search
                try:
                    row = page.get_by_text(re.compile(rf"^{re.escape(col)}$", re.I))
                    if row.count():
                        row.first.locator("xpath=ancestor::*[2]").locator("button").first.click(timeout=2000)
                        added = True
                        print(f"  added column (direct): {col}")
                except Exception as exc:
                    print(f"  warn: could not add column {col}: {exc}")

        # Apply
        try:
            page.get_by_role("button", name=re.compile(r"^Apply$", re.I)).first.click(timeout=5000)
            page.wait_for_timeout(2000)
            print("Applied Customize Columns.")
        except Exception as exc:
            print(f"Warning: could not click Apply: {exc}")
            page.keyboard.press("Escape")

    def _set_checkbox(self, page, label: str, *, checked: bool) -> None:
        try:
            box = page.get_by_label(re.compile(rf"^{label}$", re.I))
            if box.count() == 0:
                # click text then nearby checkbox
                text = page.get_by_text(re.compile(rf"^{label}$", re.I))
                if text.count():
                    # find checkbox sibling
                    cand = text.first.locator("xpath=ancestor::label[1]//input[@type='checkbox']")
                    if cand.count() == 0:
                        cand = text.first.locator("xpath=preceding::input[@type='checkbox'][1]")
                    box = cand
            if box.count() == 0:
                print(f"Warning: checkbox '{label}' not found")
                return
            el = box.first
            is_checked = el.is_checked()
            if is_checked != checked:
                el.set_checked(checked)
                page.wait_for_timeout(500)
            print(f"Checkbox {label}={'ON' if checked else 'OFF'}")
        except Exception as exc:
            print(f"Warning: could not set checkbox {label}: {exc}")

    def _download_csv(self, page, out_path: Path) -> None:
        """Click the download tray icon next to the Day dropdown (from recording)."""
        print("Clicking table toolbar download icon ...")
        download = None

        # Prefer icon near Unique / Day controls
        candidates = [
            page.locator('[aria-label*="download" i]'),
            page.locator('[aria-label*="Download" i]'),
            page.locator('[data-testid*="download" i]'),
            page.locator('button:has(svg)').filter(has_text=re.compile(r"^$")),
            page.get_by_role("button", name=re.compile(r"download|export", re.I)),
            # Often an <a> or button with download title next to Day
            page.locator('button[title*="download" i], a[title*="download" i]'),
            page.locator('button[title*="Download" i], a[title*="Download" i]'),
        ]

        # Narrow to toolbar containing "Unique" / "Day"
        toolbar = None
        try:
            toolbar = page.get_by_text(re.compile(r"^Unique$", re.I)).locator(
                "xpath=ancestor::*[contains(@class,'toolbar') or contains(@class,'header') or self::div][1]"
            )
        except Exception:
            toolbar = None

        if toolbar is not None:
            try:
                tb_btn = toolbar.locator(
                    '[aria-label*="download" i], button[title*="download" i], a[title*="download" i]'
                )
                if tb_btn.count():
                    candidates.insert(0, tb_btn)
            except Exception:
                pass

        for target in candidates:
            try:
                if not target.count():
                    continue
                loc = target.first
                if not loc.is_visible():
                    continue
                with page.expect_download(timeout=45_000) as dl_info:
                    loc.click()
                download = dl_info.value
                break
            except Exception:
                continue

        if download is None:
            shot = DOWNLOAD_DIR / "branch_export_debug.png"
            try:
                page.screenshot(path=str(shot), full_page=True)
                print(f"Debug screenshot: {shot}")
            except Exception:
                pass
            raise RuntimeError(
                "Could not click Overview table download icon. "
                "Set BRANCH_HEADED=1 and BRANCH_SUMMARY_URL to Overview. "
                f"Current URL: {page.url}"
            )

        download.save_as(str(out_path))
        name = download.suggested_filename
        if callable(name):
            name = name()
        print(f"Browser suggested filename: {name}")

    def _validate_export(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        lower = text.lower()
        # header row in Branch exports often after a short preamble
        missing = []
        for col in EXPECTED_EXPORT_COLUMNS:
            if col.lower() not in lower:
                missing.append(col)
        if missing:
            print(f"Warning: export missing expected columns: {missing}")
        else:
            print("Export contains all expected columns.")


def lookback_window(lookback_days: int, timezone: str) -> tuple[date, date]:
    today = datetime.now(ZoneInfo(timezone)).date()
    end = today - timedelta(days=1)
    start = end - timedelta(days=lookback_days - 1)
    return start, end
