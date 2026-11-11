# MCAT App Campaign Performance (Looker Studio)

A new Looker Studio report, built 2026-11-04. It is separate from the KOTC Performance Dashboard, which was not changed.

| Dashboard | Built by | Data | Link |
|---|---|---|---|
| KOTC Performance Dashboard | The owner | Real (Branch) | Not kept in this repo |
| MCAT App Campaign Performance (this report) | Claude | Real (Branch) | Not kept in this repo |
| MCAT App Campaign Performance Dashboard Demo | Claude | Sample, July 2026 | [MCAT App Campaign Performance Dashboard Demo](https://lookerstudio.google.com/reporting/41c3492f-5bfd-42f8-bf50-79a8c8802ca2) |

Links to dashboards and Sheets with real data are kept out of this repo.

- Report: the MCAT App Campaign Performance report is private to the owner and has not been shared.
- Data: an embedded data source on the Sheet Branch Data MCAT App, `Sheet1`. The report reads the Sheet with the owner's credentials.
- Funnel data: a second data source on the same Sheet's `Funnel Steps` tab, used only by the funnel chart. Looker Studio's funnel chart needs one row per step, so a single formula in `Funnel Steps!A1` turns the step columns of `Sheet1` into rows: Date, Ad Partner, Campaign, Platform, Step Order (1–5), Step and Count, with zero-count rows dropped. It recalculates when `Sheet1` changes. Its totals per step matched `Sheet1` exactly on 2026-11-08 (Clicks 1,038,944, Installs 99,400, Register 33,913, Initiate Purchases 2,005, Purchases 3,226). The chart sorts by MIN(Step Order). The Ad Partner filter and the date range both apply to it.
- Table headers: every table has header text wrapping turned on, so the full column names show instead of "…". On 2026-11-10 the By Ad Partner and By Campaign column widths were rebalanced: Cost had taken about a third of each table, and headers such as "Purchases" broke mid-word. Every header now fits on one line.
- Clicks: Branch's `clicks` column counts ad clicks reported to Branch by the ad partners, not in-app clicks. Facebook reports no clicks to Branch but has installs, and TikTok has many clicks but few attributed installs. Clicks → Installs is therefore not one user path, and the Install Rate step mixes partners.
- Context: MCAT is a to-C subscription app. The Branch data uses a 7-day attribution window. That window was set when the data was exported from Branch, so the report only labels it and cannot change it.

## Layout

Every page shares the same report-level header and filters: Ad Partner, Platform, and a date range. The date range defaults to the last 30 days, and charts compare against the previous period.

| Page | Contents |
|---|---|
| Overview | 10 scorecards (Cost, Installs, CPI, Purchases, CPP, Revenue, ROAS, Clicks, CPC, Trial Starts), each showing the change vs. the previous period. CPI, CPP and CPC use inverted colors: down is green. A daily trend chart has a previous-period line. Its optional metrics let viewers switch between 12 metrics with the metric icon on the chart. |
| Funnel | Step counts: Clicks → Installs → Register → Initiate Purchases → Purchases. Step rates: Install → Purchase, Install Rate, Register Rate, Checkout Rate, Checkout → Purchase. A funnel table by Ad Partner, and a funnel chart (Clicks → Installs → Register → Initiate Purchases → Purchases) that labels each step with its count and its % of the previous step. The funnel chart replaced the daily conversion-rate lines on 2026-11-08. |
| By Ad Partner | A heatmap table of all core metrics by partner, Cost vs. Revenue bars, CPI vs. CPP bars, and a daily trend split by partner. The trend shows daily Cost by default, and viewers can switch it to Installs, CPI, ROAS or Revenue. Its y-axis title shows the selected metric. |
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
- The funnel chart sorts by MIN(Step Order). When it was sorted by SUM(Step Order), the order depended on how many rows each step had, which gave Clicks → Initiate Purchases → Installs → Register → Purchases for July 2026. A browser tab opened before the fix may still show that order until it is reloaded.
- In the By Campaign table, long partner names such as "TikTok For Business SAN" are cut off with "…" at the current Ad Partner width.

## Demo report (sample data)

[MCAT App Campaign Performance Dashboard Demo](https://lookerstudio.google.com/reporting/41c3492f-5bfd-42f8-bf50-79a8c8802ca2) was built on 2026-11-10 as a copy of this report. It reads the sample-data Sheet [MCAT App Campaign Performance Dashboard Demo Data](https://docs.google.com/spreadsheets/d/1yJotAZ1UBTn9lE5so7YsuKIjR1T1USKOA0OFRjdbDko/edit) instead of Branch data. Every number is made up and matches the [mockup](https://claude.ai/artifact/5wNnws224sAZE7XP6ehRV1). Both the report and the Sheet are private to the owner.

The Sheet holds one month, July 2026, in four tabs:

| Tab | Rows | Used by |
|---|---|---|
| `Sheet1` | 527 (day × campaign × platform) | Overview, By Ad Partner, By Campaign, Funnel cards and table. Same headers as the real Sheet, so the copied fields work unchanged. |
| `Funnel Steps` | 2,108 | Funnel chart. Static rows for Installs → Register → Trial Starts → Purchases (Step Order 1–4). |
| `Delivery` | 527 | Health. Impressions, Reach, Clicks and Cost by day, campaign and platform. Search campaigns have no Reach. |
| `Ads` | 434 (day × ad) | Top Ads. 14 ads with Format, Cost, Impressions, Clicks, Installs, Purchases and Revenue. |

July totals: Cost $350,000, Installs 116,800 (CPI $3.00), Clicks 1,167,000 (CPC $0.30), Register 49,090, Trial Starts 5,348, Purchases 3,760, Revenue $507,614 (ROAS 1.45). These were checked in view mode against the mockup.

How the Demo differs from this report:

- The default date range is fixed to Jul 1 – Jul 31, 2026, and the header says the data is simulated with a 30-day attribution label.
- Funnel: the chart, cards and table run Installs → Register → Trial Starts → Purchases. Clicks, Install Rate, Initiate Purchases, Checkout Rate and Checkout → Purchase were replaced by Trial Starts, Register to Trial (`SUM(RC Trial Started Event) / SUM(Register)`), Trial to Paid (`SUM(Purchases) / SUM(RC Trial Started Event)`), Cost per Trial and Trial Cancel Rate.
- Health: cards for Impressions, Reach, Frequency, CPM and CTR; daily Frequency by campaign; daily CTR by ad partner; and a delivery table by campaign. Frequency is `SUM(CASE WHEN Reach > 0 THEN Impressions ELSE 0 END) / SUM(Reach)`, so search rows without reach don't inflate it. CPM is `SUM(Cost) / SUM(Impressions) * 1000` and CTR is `SUM(Clicks) / SUM(Impressions)`.
- Top Ads: one table of all 14 ads (Ad, Ad Partner, Campaign, Revenue, Impressions, Cost, CTR, Installs, Purchases, CPI, ROAS), sorted by ROAS. ROAS is `SUM(Revenue) / SUM(Cost)` and CPI is `SUM(Cost) / SUM(Installs)` on the Ads source.

Known gaps in the Demo:

- The Sheet has only July, so every "vs. previous period" comparison shows "No data".
- In the Top Ads table the Ad, Ad Partner and Campaign columns are narrow and truncate long names.
- The Health delivery table is sorted by its first metric (Frequency), not by Impressions as in the mockup.
