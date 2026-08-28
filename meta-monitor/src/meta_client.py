from __future__ import annotations

import json
from datetime import date
from typing import Any

import requests

GRAPH_API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

INSIGHT_METRICS = (
    "spend,impressions,reach,actions,unique_actions,cost_per_action_type"
)
CAMPAIGN_INSIGHT_FIELDS = f"campaign_id,campaign_name,{INSIGHT_METRICS}"
AD_INSIGHT_FIELDS = f"ad_id,ad_name,campaign_id,campaign_name,{INSIGHT_METRICS}"

BATCH_LOOKUP_SIZE = 50


class MetaClient:
    def __init__(self, access_token: str, ad_account_id: str) -> None:
        self.access_token = access_token
        self.ad_account_id = ad_account_id

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = {"access_token": self.access_token, **(params or {})}
        if path.startswith("http"):
            url = path
        elif path:
            url = f"{BASE_URL}/{path.lstrip('/')}"
        else:
            url = BASE_URL
        response = requests.get(url, params=query, timeout=60)
        response.raise_for_status()
        return response.json()

    def _paginate(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        url: str | None = None
        while True:
            if url:
                data = self._get(url, params=None)
            else:
                data = self._get(path, params)
            items.extend(data.get("data", []))
            next_url = data.get("paging", {}).get("next")
            if not next_url:
                break
            url = next_url
        return items

    def _insights_params(self, start_date: date, end_date: date) -> dict[str, Any]:
        time_range = json.dumps(
            {"since": start_date.isoformat(), "until": end_date.isoformat()}
        )
        return {
            "time_range": time_range,
            "action_report_time": "conversion",
            "use_account_attribution_setting": "true",
        }

    def _campaign_objectives(self, campaign_ids: list[str]) -> dict[str, str]:
        objectives: dict[str, str] = {}
        for i in range(0, len(campaign_ids), BATCH_LOOKUP_SIZE):
            chunk = campaign_ids[i : i + BATCH_LOOKUP_SIZE]
            data = self._get("", {"ids": ",".join(chunk), "fields": "objective"})
            for cid, payload in data.items():
                if isinstance(payload, dict):
                    objectives[cid] = payload.get("objective", "")
        return objectives

    def _ad_insights_params(
        self,
        start_date: date,
        end_date: date,
        *,
        daily: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "level": "ad",
            "fields": AD_INSIGHT_FIELDS,
            "limit": 500,
            **self._insights_params(start_date, end_date),
        }
        if daily:
            params["time_increment"] = 1
        return params

    def _account_ad_insights(
        self, start_date: date, end_date: date, *, daily: bool = False
    ) -> list[dict[str, Any]]:
        params = self._ad_insights_params(start_date, end_date, daily=daily)
        rows = self._paginate(f"{self.ad_account_id}/insights", params)
        if rows and not rows[0].get("ad_id"):
            raise ValueError(
                "Insights response is not per-ad. "
                "API call must include level=ad and a time_range."
            )
        return rows

    def _ad_insights_for_campaigns(
        self,
        campaign_ids: list[str],
        start_date: date,
        end_date: date,
        *,
        daily: bool = False,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for i in range(0, len(campaign_ids), BATCH_LOOKUP_SIZE):
            chunk = campaign_ids[i : i + BATCH_LOOKUP_SIZE]
            filtering = json.dumps(
                [{"field": "campaign.id", "operator": "IN", "value": chunk}]
            )
            params: dict[str, Any] = {
                **self._ad_insights_params(start_date, end_date, daily=daily),
                "filtering": filtering,
            }
            rows.extend(self._paginate(f"{self.ad_account_id}/insights", params))
        return rows

    def _scan_app_promotion_ad_insights(
        self,
        start_date: date,
        end_date: date,
        objective: str,
        *,
        daily: bool = False,
    ) -> list[dict[str, Any]]:
        campaigns = self._paginate(
            f"{self.ad_account_id}/campaigns",
            {"fields": "id,objective", "limit": 500},
        )
        campaign_ids = [
            c["id"] for c in campaigns if c.get("objective") == objective
        ]
        if not campaign_ids:
            return []
        return self._ad_insights_for_campaigns(
            campaign_ids, start_date, end_date, daily=daily
        )

    def _account_campaign_insights(
        self, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "level": "campaign",
            "fields": CAMPAIGN_INSIGHT_FIELDS,
            "limit": 500,
            **self._insights_params(start_date, end_date),
        }
        rows = self._paginate(f"{self.ad_account_id}/insights", params)
        if rows and not rows[0].get("campaign_id"):
            raise ValueError(
                "Insights response is account-level, not per-campaign. "
                "API call must include level=campaign and a time_range."
            )
        return rows

    def _insights_per_campaign(
        self, campaign_id: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "fields": INSIGHT_METRICS,
            **self._insights_params(start_date, end_date),
        }
        try:
            data = self._get(f"{campaign_id}/insights", params)
        except requests.HTTPError:
            params.pop("action_report_time", None)
            params.pop("use_account_attribution_setting", None)
            data = self._get(f"{campaign_id}/insights", params)
        return data.get("data", [])

    def _scan_all_app_promotion_campaigns(
        self, start_date: date, end_date: date, objective: str
    ) -> list[dict[str, Any]]:
        campaigns = self._paginate(
            f"{self.ad_account_id}/campaigns",
            {"fields": "id,name,objective", "limit": 500},
        )
        rows: list[dict[str, Any]] = []
        for campaign in campaigns:
            if campaign.get("objective") != objective:
                continue
            cid = campaign["id"]
            name = campaign.get("name", cid)
            for insight in self._insights_per_campaign(cid, start_date, end_date):
                rows.append(
                    {
                        "campaign_id": cid,
                        "campaign_name": name,
                        **insight,
                    }
                )
        return rows

    def app_promotion_insights_for_range(
        self,
        start_date: date,
        end_date: date,
        objective: str,
        campaign_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if campaign_ids:
            rows: list[dict[str, Any]] = []
            for cid in campaign_ids:
                meta = self._get(cid, {"fields": "name,objective"})
                if meta.get("objective") != objective:
                    continue
                name = meta.get("name", cid)
                for insight in self._insights_per_campaign(
                    cid, start_date, end_date
                ):
                    rows.append(
                        {
                            "campaign_id": cid,
                            "campaign_name": name,
                            **insight,
                        }
                    )
            return rows

        try:
            range_rows = self._account_campaign_insights(start_date, end_date)
        except requests.HTTPError:
            return self._scan_all_app_promotion_campaigns(
                start_date, end_date, objective
            )

        campaign_ids_found = list(
            {r["campaign_id"] for r in range_rows if r.get("campaign_id")}
        )
        if not campaign_ids_found:
            return []

        objectives = self._campaign_objectives(campaign_ids_found)
        return [
            row
            for row in range_rows
            if objectives.get(row.get("campaign_id", "")) == objective
        ]

    def app_promotion_insights_for_date(
        self,
        report_date: date,
        objective: str,
        campaign_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return self.app_promotion_insights_for_range(
            report_date, report_date, objective, campaign_ids
        )

    def _filter_app_promotion_ad_rows(
        self, ad_rows: list[dict[str, Any]], objective: str
    ) -> list[dict[str, Any]]:
        campaign_ids_found = list(
            {r["campaign_id"] for r in ad_rows if r.get("campaign_id")}
        )
        if not campaign_ids_found:
            return []

        objectives = self._campaign_objectives(campaign_ids_found)
        return [
            row
            for row in ad_rows
            if objectives.get(row.get("campaign_id", "")) == objective
        ]

    def app_promotion_ad_insights_for_range(
        self,
        start_date: date,
        end_date: date,
        objective: str,
        campaign_ids: list[str] | None = None,
        *,
        daily: bool = False,
    ) -> list[dict[str, Any]]:
        if campaign_ids:
            objectives = self._campaign_objectives(campaign_ids)
            allowed = [cid for cid in campaign_ids if objectives.get(cid) == objective]
            if not allowed:
                return []
            return self._ad_insights_for_campaigns(
                allowed, start_date, end_date, daily=daily
            )

        try:
            ad_rows = self._account_ad_insights(
                start_date, end_date, daily=daily
            )
        except requests.HTTPError:
            return self._scan_app_promotion_ad_insights(
                start_date, end_date, objective, daily=daily
            )

        return self._filter_app_promotion_ad_rows(ad_rows, objective)

    def account_currency(self) -> str:
        data = self._get(self.ad_account_id, {"fields": "currency"})
        return data.get("currency", "USD")
