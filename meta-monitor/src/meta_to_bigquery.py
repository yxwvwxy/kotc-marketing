#!/usr/bin/env python3
"""Meta app-promotion campaigns → BigQuery loader.

Writes the same campaigns the daily Slack report uses (spend > 0, US/Eastern)
into the marketing dashboard project, one row per campaign per day:

  kotc-dashboard-auto-update.meta.daily_campaign_metrics

Paired with kotc-marketing-dashboard-update `src/branch_to_bigquery.py`,
which writes Branch metrics into `branch.daily_campaign_metrics`.
Join view (not applied):
  kotc-marketing-dashboard-update/bigquery/views/meta_branch_campaign_daily.sql

Standalone — not imported by the Slack report or GitHub Actions.

Leave EXECUTE_LOAD as False so this never calls Meta for this job or writes
BigQuery.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Config
from meta_client import MetaClient
from monitor import _float, _resolve_install_metrics, past_week_range_et

EXECUTE_LOAD = False

BQ_PROJECT = "kotc-dashboard-auto-update"
BQ_DATASET = "meta"
BQ_TABLE = "daily_campaign_metrics"

META_TABLE_SCHEMA = [
    {"name": "date", "type": "DATE", "mode": "REQUIRED"},
    {"name": "campaign_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "campaign_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "spend", "type": "NUMERIC", "mode": "NULLABLE"},
    {"name": "installs", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "cpi", "type": "NUMERIC", "mode": "NULLABLE"},
    {"name": "impressions", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "reach", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "loaded_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
]


def table_id() -> str:
    project = os.environ.get("BQ_PROJECT_ID", BQ_PROJECT).strip() or BQ_PROJECT
    dataset = os.environ.get("BQ_META_DATASET", BQ_DATASET).strip() or BQ_DATASET
    table = os.environ.get("BQ_META_TABLE", BQ_TABLE).strip() or BQ_TABLE
    return f"{project}.{dataset}.{table}"


def _campaign_bq_rows(insights: list[dict[str, Any]], report_date: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for insight in insights:
        spend = _float(insight.get("spend"))
        if spend <= 0:
            continue
        campaign_id = str(insight.get("campaign_id") or "")
        installs, cpi = _resolve_install_metrics(insight, spend)
        rows.append(
            {
                "date": report_date.isoformat(),
                "campaign_id": campaign_id,
                "campaign_name": insight.get("campaign_name") or campaign_id,
                "spend": spend,
                "installs": installs,
                "cpi": cpi,
                "impressions": int(_float(insight.get("impressions"))),
                "reach": int(_float(insight.get("reach"))),
            }
        )
    return rows


def collect_meta_rows(meta: MetaClient, cfg: Config, start: date, end: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    day = start
    while day <= end:
        insights = meta.app_promotion_insights_for_date(
            day,
            cfg.campaign_objective,
            campaign_ids=cfg.campaign_ids,
        )
        rows.extend(_campaign_bq_rows(insights, day))
        day += timedelta(days=1)
    return rows


def write_bigquery(rows: list[dict[str, Any]], start: date, end: date) -> int:
    from datetime import datetime, timezone

    from google.cloud import bigquery
    from google.oauth2 import service_account

    target = table_id()
    project, dataset_name, _table = target.split(".", 2)
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if cred_path and Path(cred_path).exists():
        creds = service_account.Credentials.from_service_account_file(cred_path)
        client = bigquery.Client(project=project, credentials=creds)
    else:
        client = bigquery.Client(project=project)

    dataset_id = f"{project}.{dataset_name}"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "US"
    client.create_dataset(dataset, exists_ok=True)
    table_ref = bigquery.Table(target, schema=META_TABLE_SCHEMA)
    client.create_table(table_ref, exists_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    prepared = []
    for row in rows:
        item = dict(row)
        item["loaded_at"] = now
        prepared.append(item)

    delete_sql = f"""
    DELETE FROM `{target}`
    WHERE date BETWEEN @start_date AND @end_date
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start.isoformat()),
            bigquery.ScalarQueryParameter("end_date", "DATE", end.isoformat()),
        ]
    )
    print(f"Deleting existing rows {start} -> {end} from {target} ...")
    client.query(delete_sql, job_config=job_config).result()

    if not prepared:
        print("No rows to insert.")
        return 0

    print(f"Loading {len(prepared)} rows into {target} ...")
    load_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    client.load_table_from_json(prepared, target, job_config=load_config).result()
    return len(prepared)


def run() -> int:
    target = table_id()
    if not EXECUTE_LOAD:
        start, end = past_week_range_et()
        print(f"Meta → BigQuery  {start} -> {end}")
        print(f"Table: {target}")
        print(
            "EXECUTE_LOAD is False — Meta was not queried for this job "
            "and BigQuery was not modified."
        )
        return 0

    try:
        cfg = Config.from_env()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    start, end = past_week_range_et(cfg.report_date_override)
    print(f"Meta → BigQuery  {start} -> {end}")
    print(f"Table: {target}")

    meta = MetaClient(cfg.meta_access_token, cfg.meta_ad_account_id)
    rows = collect_meta_rows(meta, cfg, start, end)
    print(f"Rows in sync window: {len(rows)}")
    if rows:
        print("Sample row:", rows[0])
    n = write_bigquery(rows, start, end)
    print(f"Wrote {n} rows to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
