# KOTC Marketing Dashboard Update

MMP → BigQuery → Looker Studio.

Loads Branch (MMP) campaign metrics into `kotc-dashboard-auto-update.branch.daily_campaign_metrics` for Looker Studio.

```text
Branch Dashboard
  → last 7 days Summary CSV
  → convert
  → replace those dates in BigQuery
  → Looker Studio
```

Pairs with [kotc-meta-monitor](https://github.com/yxwvwxy/kotc-meta-monitor): Meta Slack report, flag and pause underperforming ads.

```text
kotc-meta-monitor                          kotc-marketing-dashboard-update
Slack report + flag/pause ads              Branch MMP → BigQuery
        \                                          /
         \                                        /
          kotc-dashboard-auto-update (BigQuery)
                    ↓
              Looker Studio
```

Meta can also land in `meta.daily_campaign_metrics` (`EXECUTE_LOAD = False`). Join SQL: `bigquery/views/meta_branch_campaign_daily.sql` (not applied).

`daily-branch-sync.yml` is the **old live job**: Playwright login → last 7 days Branch CSV → replace those dates in BigQuery. Still what Looker reads today. The new connected job is `connected-meta-mmp.yml` (manual only, does not write while `EXECUTE_LOAD` is False).

## Credentials

Local `.env`:

```bash
BRANCH_EMAIL=your@email.com
BRANCH_PASSWORD=your_password
GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json
```

Optional: `BRANCH_SUMMARY_URL`, `BRANCH_HEADED=1`.

GitHub Secrets: `BRANCH_EMAIL`, `BRANCH_PASSWORD`, `GCP_SA_KEY`.

Do not commit `.env` or the service-account JSON.

## Setup

1. GCP SA `branch-bq-sync`: BigQuery Data Editor + Job User. JSON path → `GOOGLE_APPLICATION_CREDENTIALS`.
2. `./scripts/setup_local.sh` then fill `.env`.
3. Workflow `.github/workflows/daily-branch-sync.yml` (~08:15 ET).

## Commands

```bash
./scripts/dry_run.sh     # download + convert only
./scripts/sync.sh        # replace last 7 days in BigQuery
```

Manual file: drop a Branch export in `inbox/` or:

```bash
python3 bigquery/convert_branch_export.py ~/Downloads/summary-table-export.csv
python -m src.sync_daily --from-csv /path/to/summary-table-export.csv
```

Standalone loader (not scheduled, does nothing while `EXECUTE_LOAD = False`):

```bash
python -m src.branch_to_bigquery
```

## Notes

- Default window is 7 days; those dates are deleted then reloaded.
- Numbers come from Branch as-is (`ecpi` / `ecpc` / `cpp` are not recalculated).
- `loaded_at` is ingest time only.
