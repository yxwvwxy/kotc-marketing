-- Run in BigQuery Console for project: kotc-dashboard-auto-update
-- Sandbox tip: after create, consider setting table expiration off once billing is enabled.

CREATE SCHEMA IF NOT EXISTS `kotc-dashboard-auto-update.branch`
OPTIONS (
  location = 'US',
  description = 'Branch attribution / marketing metrics for Looker Studio'
);

CREATE TABLE IF NOT EXISTS `kotc-dashboard-auto-update.branch.daily_campaign_metrics` (
  date DATE NOT NULL,
  ad_partner STRING,
  campaign STRING,
  platform STRING,
  ad_partner_3p STRING,
  clicks INT64,
  installs INT64,
  register INT64,
  complete_registration INT64,
  initiate_purchases INT64,
  purchases INT64,
  cost NUMERIC,
  revenue NUMERIC,
  ecpi NUMERIC,
  cpp NUMERIC,
  ecpc NUMERIC,
  rc_trial_cancelled_event INT64,
  rc_expiration_event INT64,
  rc_cancellation_event INT64,
  rc_trial_started_event INT64,
  rc_product_change_event INT64,
  loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY date
CLUSTER BY ad_partner, campaign, platform
OPTIONS (
  description = 'Daily Branch metrics by ad partner / campaign / platform. Existing Sheet columns + new Branch export fields.'
);
