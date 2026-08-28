# KOTC Marketing

This repo monitors Meta ads, sends a Slack report, and flags and turns off underperforming ads. It also connects the MMP to BigQuery for the Looker Studio dashboard.

```text
meta-monitor/     Meta ads → Slack report, flag & pause underperforming ads
dashboard/        Branch (MMP) → BigQuery → Looker Studio
```

Looker: [KOTC Performance Dashboard](https://datastudio.google.com/reporting/e7ebe541-bb73-4592-a0ca-6b69f654635b/page/mkyEE)

## Meta ads (`meta-monitor/`)

Daily Slack report of `OUTCOME_APP_PROMOTION` campaigns (spend, installs, CPI). Flags ads with 7-day CPI > $8. `src/pause_flagged_ads.py` can pause them (`EXECUTE_PAUSE = False` until you turn it on).

```bash
cd meta-monitor
python src/monitor.py
python scripts/preview_report.py
```

## MMP → BigQuery (`dashboard/`)

Loads Branch campaign metrics into `kotc-dashboard-auto-update.branch.daily_campaign_metrics`.

```bash
cd dashboard
./scripts/setup_local.sh
./scripts/dry_run.sh
./scripts/sync.sh
```

## Secrets

Do not commit `.env`, `local.env`, or service-account JSON. GitHub Actions needs:

- `META_ACCESS_TOKEN`, `SLACK_WEBHOOK_URL`
- `BRANCH_EMAIL`, `BRANCH_PASSWORD`, `GCP_SA_KEY`
