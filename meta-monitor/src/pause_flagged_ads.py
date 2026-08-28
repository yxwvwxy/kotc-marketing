#!/usr/bin/env python3
"""Pause ads the daily report flags (7-day CPI > $8).

Standalone only — not imported by the Slack report or GitHub Actions.
Leave EXECUTE_PAUSE as False so this never turns ads off.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Config
from meta_client import BASE_URL, BATCH_LOOKUP_SIZE, MetaClient
from monitor import (
    HIGH_CPI_AD_THRESHOLD,
    AdRow,
    _build_high_cpi_ad_rows,
    _format_cpi,
    past_week_range_et,
)

EXECUTE_PAUSE = False
STATUSES_ALREADY_OFF = frozenset({"PAUSED", "DELETED", "ARCHIVED"})


@dataclass
class PauseResult:
    ad_id: str
    name: str
    previous_status: str
    skipped: bool
    ok: bool
    error: str | None = None


def _http_error_message(exc: requests.HTTPError) -> str:
    response = exc.response
    if response is None:
        return str(exc)
    try:
        payload = response.json()
    except ValueError:
        text = (response.text or "")[:300]
        return f"HTTP {response.status_code}: {text}" if text else str(exc)
    err = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(err, dict):
        message = err.get("message") or str(exc)
        code = err.get("code")
        if code is not None:
            return f"(#{code}) {message}"
        return str(message)
    return f"HTTP {response.status_code}: {response.text[:300]}"


def _post_ad_status(meta: MetaClient, ad_id: str, status: str) -> dict[str, Any]:
    url = f"{BASE_URL}/{ad_id.lstrip('/')}"
    response = requests.post(
        url,
        data={"access_token": meta.access_token, "status": status},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def _ads_by_id(meta: MetaClient, ad_ids: list[str]) -> dict[str, dict[str, Any]]:
    ads: dict[str, dict[str, Any]] = {}
    for i in range(0, len(ad_ids), BATCH_LOOKUP_SIZE):
        chunk = ad_ids[i : i + BATCH_LOOKUP_SIZE]
        data = meta._get("", {"ids": ",".join(chunk), "fields": "id,name,status"})
        for ad_id, payload in data.items():
            if isinstance(payload, dict) and not payload.get("error"):
                ads[ad_id] = payload
    return ads


def flagged_high_cpi_ads(meta: MetaClient, cfg: Config) -> list[AdRow]:
    period_start, period_end = past_week_range_et(cfg.report_date_override)
    daily_insights = meta.app_promotion_ad_insights_for_range(
        period_start,
        period_end,
        cfg.campaign_objective,
        campaign_ids=cfg.campaign_ids,
        daily=True,
    )
    return _build_high_cpi_ad_rows(
        daily_insights,
        period_start=period_start,
        period_end=period_end,
    )


def pause_ads(meta: MetaClient, ad_ids: list[str]) -> list[PauseResult]:
    unique_ids = list(dict.fromkeys(ad_id for ad_id in ad_ids if ad_id))
    if not unique_ids:
        return []

    ads = _ads_by_id(meta, unique_ids)
    results: list[PauseResult] = []
    for ad_id in unique_ids:
        info = ads.get(ad_id)
        if not info:
            results.append(
                PauseResult(
                    ad_id=ad_id,
                    name="",
                    previous_status="",
                    skipped=False,
                    ok=False,
                    error="Ad not found",
                )
            )
            continue

        name = str(info.get("name") or "")
        status = str(info.get("status") or "")
        if status in STATUSES_ALREADY_OFF:
            results.append(
                PauseResult(
                    ad_id=ad_id,
                    name=name,
                    previous_status=status,
                    skipped=True,
                    ok=True,
                )
            )
            continue

        try:
            _post_ad_status(meta, ad_id, "PAUSED")
        except requests.HTTPError as exc:
            results.append(
                PauseResult(
                    ad_id=ad_id,
                    name=name,
                    previous_status=status,
                    skipped=False,
                    ok=False,
                    error=_http_error_message(exc),
                )
            )
            continue

        results.append(
            PauseResult(
                ad_id=ad_id,
                name=name,
                previous_status=status,
                skipped=False,
                ok=True,
            )
        )
    return results


def _print_flagged(rows: list[AdRow]) -> None:
    if not rows:
        print(f"No ads with 7-day CPI > ${HIGH_CPI_AD_THRESHOLD:.0f}.")
        return
    print(f"{len(rows)} ad(s) flagged with 7-day CPI > ${HIGH_CPI_AD_THRESHOLD:.0f}:")
    for row in rows:
        cpi = _format_cpi(row.cpi, "USD")
        print(f"  {row.ad_id}  {row.campaign_name}  {cpi}")


def run() -> int:
    try:
        cfg = Config.from_env()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    meta = MetaClient(cfg.meta_access_token, cfg.meta_ad_account_id)
    rows = flagged_high_cpi_ads(meta, cfg)
    _print_flagged(rows)

    if not EXECUTE_PAUSE:
        print("EXECUTE_PAUSE is False — ads were not changed.")
        return 0

    results = pause_ads(meta, [row.ad_id for row in rows])
    paused = sum(1 for item in results if item.ok and not item.skipped)
    failed = sum(1 for item in results if not item.ok)
    print(f"Paused {paused} ad(s); {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
