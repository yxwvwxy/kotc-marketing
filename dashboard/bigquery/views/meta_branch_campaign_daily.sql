-- Join Meta Monitor campaign spend with Branch campaign metrics.
-- Same GCP project: kotc-dashboard-auto-update
--   Meta:   meta.daily_campaign_metrics   (KOTC Meta Monitor src/meta_to_bigquery.py)
--   Branch: branch.daily_campaign_metrics (this repo src/branch_to_bigquery.py)
-- Not applied automatically. Run in BigQuery only when you want the view.

CREATE OR REPLACE VIEW `kotc-dashboard-auto-update.marketing.campaign_daily` AS
SELECT
  COALESCE(m.date, b.date) AS date,
  COALESCE(m.campaign_name, b.campaign) AS campaign,
  m.campaign_id AS meta_campaign_id,
  m.spend AS meta_spend,
  m.installs AS meta_installs,
  m.cpi AS meta_cpi,
  m.impressions AS meta_impressions,
  m.reach AS meta_reach,
  b.ad_partner AS branch_ad_partner,
  b.platform AS branch_platform,
  b.cost AS branch_cost,
  b.installs AS branch_installs,
  b.clicks AS branch_clicks,
  b.ecpi AS branch_ecpi,
  b.revenue AS branch_revenue
FROM `kotc-dashboard-auto-update.meta.daily_campaign_metrics` AS m
FULL OUTER JOIN `kotc-dashboard-auto-update.branch.daily_campaign_metrics` AS b
  ON m.date = b.date
  AND LOWER(m.campaign_name) = LOWER(b.campaign);
