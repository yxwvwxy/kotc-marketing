import os
from dataclasses import dataclass
from datetime import date
from typing import Optional

from dotenv import load_dotenv

# local.env is visible in Finder; .env is optional (hidden dotfile)
load_dotenv("local.env")
load_dotenv(".env")

DEFAULT_AD_ACCOUNT_ID = "act_972808873202575"
DEFAULT_CAMPAIGN_OBJECTIVE = "OUTCOME_APP_PROMOTION"
REPORT_TIMEZONE = "America/New_York"


def _campaign_ids() -> Optional[list[str]]:
    raw = os.getenv("META_CAMPAIGN_IDS", "").strip()
    if not raw:
        return None
    return [c.strip() for c in raw.split(",") if c.strip()]


def _parse_date(raw: str, env_name: str) -> date:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            from datetime import datetime

            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(
        f"Invalid {env_name} '{raw}'. Use YYYY-MM-DD or MM/DD/YYYY."
    )


def _report_date_override() -> Optional[date]:
    raw = os.getenv("REPORT_DATE", "").strip()
    if not raw:
        return None
    return _parse_date(raw, "REPORT_DATE")


def _report_week_end_override() -> Optional[date]:
    raw = os.getenv("REPORT_WEEK_END", "").strip()
    if not raw:
        return None
    return _parse_date(raw, "REPORT_WEEK_END")


@dataclass(frozen=True)
class Config:
    meta_access_token: str
    meta_ad_account_id: str
    slack_webhook_url: str
    campaign_objective: str
    campaign_ids: Optional[list[str]]
    report_date_override: Optional[date]
    report_week_end_override: Optional[date]

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("META_ACCESS_TOKEN", "").strip()
        account = os.getenv("META_AD_ACCOUNT_ID", DEFAULT_AD_ACCOUNT_ID).strip()
        webhook = os.getenv("SLACK_WEBHOOK_URL", "").strip()

        missing = [
            name
            for name, val in [
                ("META_ACCESS_TOKEN", token),
                ("SLACK_WEBHOOK_URL", webhook),
            ]
            if not val
        ]
        if missing:
            raise ValueError(
                f"Missing required env vars: {', '.join(missing)}. "
                "Copy .env.example to .env and fill in values."
            )

        if not account.startswith("act_"):
            account = f"act_{account}"

        return cls(
            meta_access_token=token,
            meta_ad_account_id=account,
            slack_webhook_url=webhook,
            campaign_objective=os.getenv(
                "META_CAMPAIGN_OBJECTIVE", DEFAULT_CAMPAIGN_OBJECTIVE
            ).strip()
            or DEFAULT_CAMPAIGN_OBJECTIVE,
            campaign_ids=_campaign_ids(),
            report_date_override=_report_date_override(),
            report_week_end_override=_report_week_end_override(),
        )
