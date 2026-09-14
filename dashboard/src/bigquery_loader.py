from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from google.cloud import bigquery
from google.oauth2 import service_account

OUT_COLS = [
    "date",
    "ad_partner",
    "campaign",
    "platform",
    "ad_partner_3p",
    "clicks",
    "installs",
    "register",
    "complete_registration",
    "initiate_purchases",
    "purchases",
    "cost",
    "revenue",
    "ecpi",
    "cpp",
    "ecpc",
    "rc_trial_cancelled_event",
    "rc_expiration_event",
    "rc_cancellation_event",
    "rc_trial_started_event",
    "rc_product_change_event",
    "loaded_at",
]

INT_COLS = {
    "clicks",
    "installs",
    "register",
    "complete_registration",
    "initiate_purchases",
    "purchases",
    "rc_trial_cancelled_event",
    "rc_expiration_event",
    "rc_cancellation_event",
    "rc_trial_started_event",
    "rc_product_change_event",
}

# Missing Branch events stay NULL — do not invent 0.
NULLABLE_INT_COLS = {
    "register",
    "rc_trial_cancelled_event",
    "rc_expiration_event",
    "rc_cancellation_event",
    "rc_trial_started_event",
    "rc_product_change_event",
}

MONEY_COLS = {"cost", "revenue", "ecpi", "cpp", "ecpc"}


def _to_number(v: Any, *, default_zero: bool = True) -> float | None:
    if v in (None, ""):
        return 0.0 if default_zero else None
    return float(v)


def _prepare_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    prepared = []
    # Ratios: keep null unless Branch provided a value (do not invent 0).
    ratio_cols = {"ecpi", "cpp", "ecpc"}
    for r in rows:
        item: dict[str, Any] = {}
        item["date"] = r["date"]
        item["ad_partner"] = r.get("ad_partner")
        item["campaign"] = r.get("campaign")
        item["platform"] = r.get("platform")
        item["ad_partner_3p"] = r.get("ad_partner_3p")
        for c in INT_COLS:
            v = r.get(c)
            if v not in (None, ""):
                item[c] = int(v)
            else:
                item[c] = None if c in NULLABLE_INT_COLS else 0
        for c in MONEY_COLS:
            item[c] = _to_number(r.get(c), default_zero=(c not in ratio_cols))
        item["loaded_at"] = r.get("loaded_at") or now
        prepared.append(item)
    return prepared


class BigQueryLoader:
    def __init__(self, table_id: str):
        self.table_id = table_id
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        if cred_path and Path(cred_path).exists():
            creds = service_account.Credentials.from_service_account_file(cred_path)
            project = table_id.split(".", 1)[0] if "." in table_id else None
            self.client = bigquery.Client(project=project, credentials=creds)
        else:
            self.client = bigquery.Client()

    def append_rows(self, rows: list[dict[str, Any]]) -> int:
        """Append rows only — does not delete existing data."""
        prepared = _prepare_rows(rows)
        if not prepared:
            print("No rows to insert.")
            return 0

        print(f"Appending {len(prepared)} rows into {self.table_id} ...")
        load_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        )
        load_job = self.client.load_table_from_json(
            prepared,
            self.table_id,
            job_config=load_config,
        )
        load_job.result()
        return len(prepared)

    def replace_date_range(self, rows: list[dict[str, Any]], start: date, end: date) -> int:
        """Delete [start, end] then load rows via load job (idempotent)."""
        prepared = _prepare_rows(rows)

        delete_sql = f"""
        DELETE FROM `{self.table_id}`
        WHERE date BETWEEN @start_date AND @end_date
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_date", "DATE", start.isoformat()),
                bigquery.ScalarQueryParameter("end_date", "DATE", end.isoformat()),
            ]
        )
        print(f"Deleting existing rows {start} -> {end} from {self.table_id} ...")
        self.client.query(delete_sql, job_config=job_config).result()

        if not prepared:
            print("No rows to insert.")
            return 0

        print(f"Loading {len(prepared)} rows into {self.table_id} ...")
        load_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        )
        load_job = self.client.load_table_from_json(
            prepared,
            self.table_id,
            job_config=load_config,
        )
        load_job.result()
        return len(prepared)
