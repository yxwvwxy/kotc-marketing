# KOTC Marketing

This repo monitors Meta ads, sends a Slack report, and flags and turns off underperforming ads. It also connects the MMP to BigQuery for the Looker Studio dashboard.

Local folder and GitHub repo are the same name: `kotc-marketing`.

```text
meta-monitor/   Slack daily report (running)
                flag 7-day CPI > $8
                pause_flagged_ads.py (not running)

dashboard/      inbox drag-and-drop → BigQuery (running locally)
                branch_to_bigquery.py (not running)
```

Looker: [KOTC Performance Dashboard](https://datastudio.google.com/reporting/e7ebe541-bb73-4592-a0ca-6b69f654635b/page/mkyEE)

## Running

**Slack report** — GitHub Action `daily-report.yml` (~11 AM ET). Preview locally:

```bash
cd meta-monitor
python src/monitor.py
python scripts/preview_report.py
```

**Inbox → BigQuery** — drop a Branch export into `inbox/` (or `dashboard/inbox/`):

```bash
cd dashboard
./scripts/setup_local.sh
./scripts/install_inbox_watch.sh
```

## Not running

These programs exist but do not execute until you flip the flag:

- `meta-monitor/src/pause_flagged_ads.py` — `EXECUTE_PAUSE = False`
- `dashboard/src/branch_to_bigquery.py` — `EXECUTE_LOAD = False` (no scheduled Branch sync)

## Secrets

Do not commit `.env`, `local.env`, or service-account JSON.

GitHub Actions (Slack): `META_ACCESS_TOKEN`, `SLACK_WEBHOOK_URL`  
Local inbox: `BRANCH_EMAIL`, `BRANCH_PASSWORD`, `GOOGLE_APPLICATION_CREDENTIALS` in `dashboard/.env`
