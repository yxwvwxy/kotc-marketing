# KOTC Meta Monitor

Meta ads monitor: daily Slack report, flag underperforming ads, turn them off.

- **Report** — each `OUTCOME_APP_PROMOTION` campaign with spend yesterday (US/Eastern): spend, installs, CPI, impressions, reach. Slack at ~11:00 AM ET.
- **Flag** — ads with 7-day CPI > $8 (and spend on at least 5 of those days).
- **Pause** — `src/pause_flagged_ads.py` can set those ads to `PAUSED` in Meta. Not scheduled; `EXECUTE_PAUSE = False` until you turn it on.

Pairs with [kotc-marketing-dashboard-update](https://github.com/yxwvwxy/kotc-marketing-dashboard-update): Branch MMP → BigQuery → Looker Studio.

```text
kotc-meta-monitor                          kotc-marketing-dashboard-update
Slack report + flag/pause ads              Branch MMP → BigQuery
        \                                          /
         \                                        /
          kotc-dashboard-auto-update (BigQuery)
                    ↓
              Looker Studio
```

## Slack report

```
KOTC Meta App Install Campaign Daily Report
Date: 06/03/2026

Campaign Name          Amount Spent  Installs  CPI     Impression  Reach
Old App Campaign       $159.91       14        $11.42  18,864      17,668
Total                  $159.91       14        $11.42  18,864      17,668
```

One row per campaign. App promotion only, spend > 0 that day.

## Run locally

Put `META_ACCESS_TOKEN` and `SLACK_WEBHOOK_URL` in `local.env`.

```bash
cd "/Users/vivienneyang/Projects/KOTC Meta Monitor"
source .venv/bin/activate
pip install -r requirements.txt
python src/monitor.py                 # posts Slack
python scripts/preview_report.py      # print only, no Slack
```

Optional: `REPORT_DATE=2026-06-03` or `META_CAMPAIGN_IDS=23855562694380330`.

## GitHub Actions

`.github/workflows/daily-report.yml` ~11 AM ET.

Secrets: `META_ACCESS_TOKEN`, `SLACK_WEBHOOK_URL`. Renew the Meta token when it expires (~60 days).

## Pause flagged ads

```bash
python src/pause_flagged_ads.py
```

Needs `ads_management` on the token. Does nothing while `EXECUTE_PAUSE` is `False`.

## Meta → BigQuery

`src/meta_to_bigquery.py` can write the same campaign rows to `kotc-dashboard-auto-update.meta.daily_campaign_metrics`. `EXECUTE_LOAD = False`; not scheduled.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Graph API returns one account-level row | Insights need `level=campaign` |
| Installs 0 but spend > 0 | Check `omni_app_install`; CPI may come from `cost_per_action_type` |
