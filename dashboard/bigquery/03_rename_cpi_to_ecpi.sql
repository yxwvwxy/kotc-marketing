-- Run once in BigQuery if the table still has column `cpi`.
ALTER TABLE `kotc-dashboard-auto-update.branch.daily_campaign_metrics`
RENAME COLUMN cpi TO ecpi;
