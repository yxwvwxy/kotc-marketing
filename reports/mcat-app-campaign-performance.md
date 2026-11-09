# MCAT App Campaign Performance (Looker Studio)

A new Looker Studio report, built 2026-11-04. It is separate from the KOTC Performance Dashboard, which was not changed.

- Report: [MCAT App Campaign Performance](https://lookerstudio.google.com/reporting/25d33782-219b-4456-8e65-4beb8e66830c). It is private to the owner and has not been shared.
- Data: an embedded data source on the Sheet [Branch Data MCAT App](https://docs.google.com/spreadsheets/d/1-H_EV3dqF62blGc4p2F7CwQvInbGbgQT7TvsFmkgnhs/edit), `Sheet1`. The report reads the Sheet with the owner's credentials.
- Funnel data: a second data source on the same Sheet's `Funnel Steps` tab, used only by the funnel chart. Looker Studio's funnel chart needs one row per step, so a single formula in `Funnel Steps!A1` turns the step columns of `Sheet1` into rows: Date, Ad Partner, Campaign, Platform, Step Order (1–5), Step and Count, with zero-count rows dropped. It recalculates when `Sheet1` changes. Its totals per step matched `Sheet1` exactly on 2026-11-08 (Clicks 1,038,944, Installs 99,400, Register 33,913, Initiate Purchases 2,005, Purchases 3,226). The chart sorts by MIN(Step Order). The Ad Partner filter and the date range both apply to it.
- Table headers: every table has header text wrapping turned on, so the full column names show instead of "…".
- Context: MCAT is a to-C subscription app. The Branch data uses a 7-day attribution window. That window was set when the data was exported from Branch, so the report only labels it and cannot change it.

## Layout

Every page shares the same report-level header and filters: Ad Partner, Platform, and a date range. The date range defaults to the last 30 days, and charts compare against the previous period.

| Page | Contents |
|---|---|
| Overview | 10 scorecards (Cost, Installs, CPI, Purchases, CPP, Revenue, ROAS, Clicks, CPC, Trial Starts), each showing the change vs. the previous period. CPI, CPP and CPC use inverted colors: down is green. A daily trend chart has a previous-period line. Its optional metrics let viewers switch between 12 metrics with the metric icon on the chart. |
| Funnel | Step counts: Clicks → Installs → Register → Initiate Purchases → Purchases. Step rates: Install → Purchase, Install Rate, Register Rate, Checkout Rate, Checkout → Purchase. A funnel table by Ad Partner, and a funnel chart (Clicks → Installs → Register → Initiate Purchases → Purchases) that labels each step with its count and its % of the previous step. The funnel chart replaced the daily conversion-rate lines on 2026-11-08. |
| By Ad Partner | A heatmap table of all core metrics by partner, Cost vs. Revenue bars, CPI vs. CPP bars, and a daily trend split by partner (with optional metrics). |
| By Campaign | A heatmap table by Ad Partner × Campaign (paginated), plus bar charts of Cost by campaign and ROAS by campaign. |
| Health | Placeholder. The planned metrics are Impressions, Reach, Frequency, CPM and CTR. |
| Top Ads | Placeholder. The planned table is Ad, Partner, Campaign, Cost, Impressions, CTR, Installs, CPI, Purchases, Revenue and ROAS. |

Health and Top Ads are left empty on purpose. The Sheet has no impression, reach or ad-level columns, so these pages need ad-level delivery data, for example a Meta ads sheet fed by `meta-monitor`.

## Data source fields

- The Sheet's own `CPI`, `CPP` and `ECPC` columns are per-row ratios, which are wrong once rows are summed. They were renamed `CPI (sheet)`, `CPP (sheet)` and `eCPC (sheet)`, and no chart uses them.
- `Cost`, `Revenue` and all cost-type fields are formatted as USD. Rates are formatted as percent.

Calculated fields:

| Field | Formula |
|---|---|
| CPI | `SUM(Cost) / SUM(Installs)` |
| CPC | `SUM(Cost) / SUM(Clicks)` |
| CPP | `SUM(Cost) / SUM(Purchases)` |
| ROAS | `SUM(Revenue) / SUM(Cost)` |
| Install Rate | `SUM(Installs) / SUM(Clicks)` |
| Register Rate | `SUM(Register) / SUM(Installs)` |
| Checkout Rate | `SUM(Initiate Purchases) / SUM(Register)` |
| Checkout to Purchase | `SUM(Purchases) / SUM(Initiate Purchases)` |
| Purchase Rate | `SUM(Purchases) / SUM(Installs)` |
| Revenue per Install | `SUM(Revenue) / SUM(Installs)` |
| ARPPU | `SUM(Revenue) / SUM(Purchases)` |
| Cost per Trial | `SUM(Cost) / SUM(RC Trial Started Event)` |
| Trial Cancel Rate | `SUM(RC Trial Cancelled Event) / SUM(RC Trial Started Event)` |

`RC Trial Started Event` is displayed as **Trial Starts** in the charts.

## Checks and data caveats

- July 2026 was checked against the local BigQuery backup and matched exactly: Cost $1,721.26, Installs 2,883, Purchases 278, Revenue $8,952.49, Clicks 15,782, CPI $0.60, CPP $6.19, ROAS 5.2.
- The data ends 2026-09-30, and September has cost and clicks but no installs, purchases or revenue. August installs are also about one-fifth of normal. As a result, the default last 30 days shows "No data". Pick a range that ends by July 2026 to see complete data.
- The `rc_*` (RevenueCat) columns only start in August 2026, so Trial Starts, Cost per Trial and Trial Cancel Rate are empty before then.
- In July 2026, Facebook has 2,065 installs with $0 cost and 0 clicks in the Branch data. Its CPI and Install Rate therefore come out empty, and the blended CPI is understated.
- Purchases exceed Initiate Purchases (for example, Checkout → Purchase is 128% in July 2026), because not every purchase records a checkout event.

## Not done yet

- Health and Top Ads have no data source yet.
- The By Campaign table has a fixed height and is paginated.
- In the funnel chart, Clicks is far larger than the later steps (15,782 vs. 278 purchases in July 2026), so the bars after Clicks render as thin lines. The owner chose on 2026-11-08 to keep Clicks as the first step anyway.
- The By Ad Partner and By Campaign tables have header wrapping on, but some columns may still be narrow enough to break a word such as "Purchases" mid-word. This was not checked in view mode, because Google showed a reCAPTCHA. The By Ad Partner table's header font was changed from 14px to 12px.
