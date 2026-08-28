from __future__ import annotations

import os
from dataclasses import dataclass


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def _optional(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    branch_email: str
    branch_password: str
    branch_summary_url: str
    branch_headed: bool
    bq_project_id: str
    bq_dataset: str
    bq_table: str
    lookback_days: int
    timezone: str

    @property
    def table_id(self) -> str:
        return f"{self.bq_project_id}.{self.bq_dataset}.{self.bq_table}"

    @classmethod
    def from_env(cls, *, require_branch_login: bool = True) -> "Settings":
        headed = _optional("BRANCH_HEADED", "0").lower() in {"1", "true", "yes"}
        if require_branch_login:
            email = _require("BRANCH_EMAIL")
            password = _require("BRANCH_PASSWORD")
        else:
            email = _optional("BRANCH_EMAIL")
            password = _optional("BRANCH_PASSWORD")
        return cls(
            branch_email=email,
            branch_password=password,
            branch_summary_url=_optional("BRANCH_SUMMARY_URL"),
            branch_headed=headed,
            bq_project_id=_optional("BQ_PROJECT_ID", "kotc-dashboard-auto-update"),
            bq_dataset=_optional("BQ_DATASET", "branch"),
            bq_table=_optional("BQ_TABLE", "daily_campaign_metrics"),
            lookback_days=int(_optional("SYNC_LOOKBACK_DAYS", "7") or "7"),
            timezone=_optional("SYNC_TIMEZONE", "America/New_York") or "America/New_York",
        )
