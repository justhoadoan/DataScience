# Data dictionary

The original 18 input columns are preserved; analysis fields are separate. Missing values are retained, with no imputation during EDA. Original Vietnamese listing text, category codes and place names remain unchanged; English labels are used for presentation.

| field | dtype | description |
| --- | --- | --- |
| source | str | Source website; used to diagnose sample composition. |
| listing_id | str | Source-prefixed listing ID; never a predictor. |
| category | str | Original source category; does not guarantee residential scope. |
| url | str | Original listing URL for verification; never a predictor. |
| title | str | Original Vietnamese title; may contain prices, excluded from baseline predictors. |
| price_vnd | int64 | Numeric price from the existing pipeline, preserved unchanged. |
| price_raw | str | Original price text for unit verification; never a predictor. |
| area_m2 | float64 | Original numeric area; its meaning may differ across property categories. |
| area_raw | float64 | Original area field from the existing pipeline, retained for verification. |
| bedrooms | float64 | Original bedroom count; may describe an entire building. |
| toilets | float64 | Original bathroom count; structured on Nhatot, text-derived on Alonhadat. |
| furniture | str | Original furnishing label; missing does not mean unfurnished. |
| city | str | Original city name. |
| district | str | Original district name; not verified against current administrative boundaries. |
| ward | str | Original ward/commune name; do not join across sources using name alone. |
| location_raw | str | Original location text. |
| posted_date | str | Source posting date; does not measure vacancy duration. |
| scraped_at | str | Parser execution date, NOT a verified download date. |
| price_month_vnd | float64 | Verified monthly asking rent in VND; missing if price/unit is unresolved. Proposed target. |
| price_unit_status | str | Raw/numeric price validation result; per_m2_total_verified must not be multiplied again. |
| district_analysis | str | NFC and whitespace-normalized district; no administrative remapping. |
| scope_flag | str | normal = not flagged by scope rules; suspicious = contextual review required. |
| duplicate_group_id | str | Candidate group from ID/URL or normalized title + district/ward/category, independent of price. Not a verified unique property. |
| area_analysis_m2 | float64 | Finite area >5 m²; missing when review is pending or excludes area. |
| bedrooms_analysis | float64 | Separate sleeping rooms; explicit studio is 0, unknown stays missing. Conflicting or implausible layouts are not used as features. |
| toilets_analysis | float64 | Nonnegative integer; values >10, or >5 for rooms, are missing because they may count an entire building. |
| bedrooms_origin | str | Evidence for separate bedrooms: title_explicit, structured, unknown, unverified_source_room_count, title_ambiguous, source_title_conflict or implausible_layout. |
| quality_flags | str | Semicolon-separated flags. A flag does not automatically exclude a row. |
| scope_decision | str | keep/exclude/unresolved or blank; contextual scope review decision. |
| price_decision | str | keep/exclude/unresolved or blank; keep does not override a parser validation failure. |
| area_decision | str | keep/exclude/unresolved or blank; affects area, not monthly rent eligibility by itself. |
| review_note | str | Review evidence, context and decision limitations. |
| reviewer | str | Person/agent that read the context; does not imply website verification. |
| review_status | str | pending for unresolved scope/price/area; reviewed when a decision exists; otherwise not_required. Duplicate/count flags may remain unverified. |
| exclusion_reason | str | Reason for exclusion from the monthly price set; empty when included. Not a separate price/m² exclusion reason. |
| include_price | bool | Boolean membership of the residential monthly asking-rent set under the audit policy. |
| include_ppm2 | bool | Boolean membership of the primary price/m² set: include_price, apartment/room category and usable area. |
| price_million | float64 | price_month_vnd / 1e6; never a predictor. |
| price_per_m2 | float64 | price_month_vnd / area_analysis_m2; secondary metric, exploratory for houses; never a predictor. |
| log_price | float64 | ln(price_month_vnd); alternative target, never a predictor. |
| log_area | float64 | ln(area_analysis_m2). |
| furniture_analysis | str | English furnishing label: Furnished, Unfurnished or Unknown; no unfurnished imputation. |
| furniture_origin | str | structured/text_derived according to the source adapter. |
| toilets_origin | str | structured/text_derived according to the source adapter. |
| area_band | str | Fixed category-specific [left, right) interval; Unknown when missing. |
| bedroom_group | str | 0/1/2/3/4+/Unknown derived from bedrooms_analysis. |
| split_group | str | Candidate duplicate group or a unique group for a single listing; used for proposed group splitting. |

## Area-band boundaries

- Apartments (can_ho_chung_cu): [0, 40, 60, 80, 100, 150, inf], left-closed/right-open intervals, m².
- Rental rooms (nha_tro): [0, 20, 30, 40, 60, inf], left-closed/right-open intervals, m².

The review queue stores review decisions and the current review list. Edit *_decision, review_note and reviewer, then rerun the audit. Saved decisions are rejected if title/price_raw/area_raw changes. Do not delete rows from the input.
