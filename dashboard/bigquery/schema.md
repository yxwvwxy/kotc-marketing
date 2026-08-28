# Branch metrics — BigQuery schema

Project: `kotc-dashboard-auto-update`  
Dataset: `branch`  
Table: `daily_campaign_metrics`

## Column mapping

| BigQuery column | Existing Sheet | New Branch export | Type |
|---|---|---|---|
| `date` | Date | date | DATE |
| `ad_partner` | Ad Partner | ad partner | STRING |
| `campaign` | Campaign | campaign | STRING |
| `platform` | Platform | platform | STRING |
| `ad_partner_3p` | — **NEW** | ad partner (3p) | STRING |
| `clicks` | Clicks | clicks | INT64 |
| `installs` | Installs | installs | INT64 |
| `register` | Register | REGISTER | INT64 |
| `complete_registration` | Complete Registration | COMPLETE_REGISTRATION | INT64 |
| `initiate_purchases` | Initiate Purchases | INITIATE_PURCHASE | INT64 |
| `purchases` | Purchases | PURCHASE | INT64 |
| `cost` | Cost | cost | NUMERIC |
| `revenue` | Revenue | revenue | NUMERIC |
| `ecpi` | CPI *(历史 Sheet)* | eCPI | NUMERIC |
| `cpp` | CPP | — *(export 里没有，可空)* | NUMERIC |
| `ecpc` | — **NEW** | eCPC | NUMERIC |
| `rc_trial_cancelled_event` | — **NEW** | rc_trial_cancelled_event | INT64 |
| `rc_expiration_event` | — **NEW** | rc_expiration_event | INT64 |
| `rc_cancellation_event` | — **NEW** | rc_cancellation_event | INT64 |
| `rc_trial_started_event` | — **NEW** | rc_trial_started_event | INT64 |
| `rc_product_change_event` | — **NEW** | rc_product_change_event | INT64 |
| `loaded_at` | — *(写入时自动填)* | — | TIMESTAMP |

## Notes

- Sheet 里的 `Purchases` 带 `$` 格式，按数字解析为购买次数（与新 export 的 `PURCHASE` 一致）。
- 统一使用字段名 `ecpi`（对应 Branch `eCPI`；历史 Sheet 的 CPI 也映射到此列）。
- RevenueCat 相关 5 个 `rc_*` 事件列为新增；历史 Sheet 导入时填 `0` 或 `NULL`。
