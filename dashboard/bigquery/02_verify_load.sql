-- Run after uploading data into branch.daily_campaign_metrics

SELECT COUNT(*) AS row_count,
       MIN(date) AS min_date,
       MAX(date) AS max_date,
       COUNTIF(ad_partner_3p IS NOT NULL) AS rows_with_3p,
       COUNTIF(ecpc IS NOT NULL) AS rows_with_ecpc,
       SUM(installs) AS total_installs,
       SUM(cost) AS total_cost
FROM `kotc-dashboard-auto-update.branch.daily_campaign_metrics`;
