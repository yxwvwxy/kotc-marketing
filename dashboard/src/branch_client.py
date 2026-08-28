from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import requests

QUERY_URL = "https://api2.branch.io/v1/query/analytics"

# Matches summary-table export dimensions as closely as Query API allows.
DIMENSIONS = [
    "last_attributed_touch_data_tilde_advertising_partner_name",
    "last_attributed_touch_data_tilde_campaign",
    "user_data_platform",
    "last_attributed_touch_data_tilde_advertising_partner_id",
]

# Custom / commerce event names as they appear in Branch exports.
CUSTOM_EVENTS = {
    "register": "REGISTER",
    "complete_registration": "COMPLETE_REGISTRATION",
    "initiate_purchases": "INITIATE_PURCHASE",
    "purchases": "PURCHASE",
    "rc_trial_cancelled_event": "rc_trial_cancelled_event",
    "rc_expiration_event": "rc_expiration_event",
    "rc_cancellation_event": "rc_cancellation_event",
    "rc_trial_started_event": "rc_trial_started_event",
    "rc_product_change_event": "rc_product_change_event",
}


class BranchQueryClient:
    def __init__(self, branch_key: str, branch_secret: str, timezone: str = "America/New_York"):
        self.branch_key = branch_key
        self.branch_secret = branch_secret
        self.tz = ZoneInfo(timezone)
        self.session = requests.Session()
        self._last_call = 0.0

    def _throttle(self) -> None:
        # Stay under ~5 req/sec and leave margin for 20/min.
        elapsed = time.time() - self._last_call
        if elapsed < 0.25:
            time.sleep(0.25 - elapsed)
        self._last_call = time.time()

    def _date_bounds(self, day: date) -> tuple[str, str]:
        # Query API expects ISO-8601 dates only (YYYY-MM-DD); app timezone is applied by Branch.
        day_str = day.isoformat()
        return day_str, day_str

    def query(
        self,
        *,
        start_date: str,
        end_date: str,
        data_source: str,
        aggregation: str,
        dimensions: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        dims = list(dimensions or DIMENSIONS)
        payload: dict[str, Any] = {
            "branch_key": self.branch_key,
            "branch_secret": self.branch_secret,
            "start_date": start_date,
            "end_date": end_date,
            "data_source": data_source,
            "aggregation": aggregation,
            "granularity": "day",
            "dimensions": dims,
            "limit": limit,
        }
        if filters:
            payload["filters"] = filters

        self._throttle()
        resp = self.session.post(QUERY_URL, json=payload, timeout=120)
        # Some apps reject advertising_partner_id; retry without it.
        if resp.status_code >= 400 and "advertising_partner_id" in ",".join(dims):
            dims = [d for d in dims if d != "last_attributed_touch_data_tilde_advertising_partner_id"]
            payload["dimensions"] = dims
            self._throttle()
            resp = self.session.post(QUERY_URL, json=payload, timeout=120)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Branch Query API {resp.status_code} for {data_source}/{aggregation}: {resp.text[:800]}"
            )
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("results", "data", "result"):
                if isinstance(data.get(key), list):
                    return data[key]
        raise RuntimeError(f"Unexpected Branch response shape: {str(data)[:500]}")

    def fetch_day_metrics(self, day: date) -> list[dict[str, Any]]:
        """Pull one calendar day and merge into table-shaped rows."""
        start, end = self._date_bounds(day)
        buckets: dict[tuple, dict[str, Any]] = {}

        def key_from(row: dict[str, Any]) -> tuple:
            # Use Branch values as-is; do not substitute labels like "Unpopulated".
            def raw(v: Any) -> str | None:
                if v in (None, "", "null"):
                    return None
                return str(v)

            partner = raw(row.get("last_attributed_touch_data_tilde_advertising_partner_name"))
            campaign = raw(row.get("last_attributed_touch_data_tilde_campaign"))
            platform = raw(row.get("user_data_platform"))
            partner_3p = raw(row.get("last_attributed_touch_data_tilde_advertising_partner_id"))
            return (day.isoformat(), partner, campaign, platform, partner_3p)

        def ensure(row: dict[str, Any]) -> dict[str, Any]:
            k = key_from(row)
            if k not in buckets:
                buckets[k] = {
                    "date": day.isoformat(),
                    "ad_partner": k[1],
                    "campaign": k[2],
                    "platform": k[3],
                    "ad_partner_3p": k[4],
                    "clicks": 0,
                    "installs": 0,
                    "register": 0,
                    "complete_registration": 0,
                    "initiate_purchases": 0,
                    "purchases": 0,
                    "cost": Decimal("0"),
                    "revenue": Decimal("0"),
                    # Only filled if Branch returns them — never computed locally.
                    "ecpi": None,
                    "cpp": None,
                    "ecpc": None,
                    "rc_trial_cancelled_event": 0,
                    "rc_expiration_event": 0,
                    "rc_cancellation_event": 0,
                    "rc_trial_started_event": 0,
                    "rc_product_change_event": 0,
                }
            return buckets[k]

        def add_count(rows: list[dict[str, Any]], field: str) -> None:
            for row in rows:
                dest = ensure(row)
                dest[field] += int(row.get("total_count") or row.get("unique_count") or 0)

        # Clicks / installs
        add_count(
            self.query(
                start_date=start,
                end_date=end,
                data_source="eo_click",
                aggregation="total_count",
            ),
            "clicks",
        )
        add_count(
            self.query(
                start_date=start,
                end_date=end,
                data_source="eo_install",
                aggregation="unique_count",
            ),
            "installs",
        )

        # Custom events (try common filter keys used by Branch apps)
        for field, event_name in CUSTOM_EVENTS.items():
            rows: list[dict[str, Any]] = []
            last_err: Exception | None = None
            for filter_key in ("name", "event", "event_name"):
                try:
                    rows = self.query(
                        start_date=start,
                        end_date=end,
                        data_source="eo_custom_event",
                        aggregation="total_count",
                        filters={filter_key: [event_name]},
                    )
                    last_err = None
                    break
                except Exception as exc:  # noqa: BLE001 - try next filter key
                    last_err = exc
                    continue
            if last_err and not rows:
                print(f"  warn: custom event {event_name} skipped: {last_err}")
            else:
                add_count(rows, field)

        # Commerce revenue (and purchase count already pulled as PURCHASE custom event;
        # also add eo_commerce_event revenue).
        for row in self.query(
            start_date=start,
            end_date=end,
            data_source="eo_commerce_event",
            aggregation="revenue",
        ):
            dest = ensure(row)
            dest["revenue"] += Decimal(str(row.get("revenue") or 0))

        # SAN / partner cost
        for row in self.query(
            start_date=start,
            end_date=end,
            data_source="cost",
            aggregation="cost",
        ):
            dest = ensure(row)
            dest["cost"] += Decimal(str(row.get("cost") or row.get("total_count") or 0))

        # Keep Branch-provided fields only. Do not locally compute ecpi/ecpc/cpp.
        out = []
        for row in buckets.values():
            for money in ("cost", "revenue", "ecpi", "cpp", "ecpc"):
                val = row.get(money)
                if val is None:
                    row[money] = None
                elif val == 0 or val == Decimal("0"):
                    row[money] = "0"
                else:
                    row[money] = f"{Decimal(str(val)):.6f}".rstrip("0").rstrip(".")
            out.append(row)
        return out

    def fetch_range(self, start_day: date, end_day: date) -> list[dict[str, Any]]:
        if end_day < start_day:
            raise ValueError("end_day must be >= start_day")
        # Query API max window is 7 days; we fetch day-by-day for simpler merging.
        rows: list[dict[str, Any]] = []
        day = start_day
        while day <= end_day:
            print(f"Fetching Branch metrics for {day.isoformat()} ...")
            day_rows = self.fetch_day_metrics(day)
            print(f"  -> {len(day_rows)} rows")
            rows.extend(day_rows)
            day += timedelta(days=1)
        return rows
