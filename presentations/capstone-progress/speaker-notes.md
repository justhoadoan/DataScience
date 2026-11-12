# Hanoi Rent Insight — five-minute progress report

Use this as a short group progress update. Explain objectives, early sample work and proposed design. Do not add final model scores, a production demo or claims of completed deployment. Slides 6–7 show real raw sources and matching CSV rows; the UI on slide 10 is a screenshot of the actual local application.

## Timing

| Slide | Topic | Duration | Elapsed time |
| --- | --- | ---: | --- |
| 1 | Project introduction | 10 seconds | 0:00–0:10 |
| 2 | Objective | 20 seconds | 0:10–0:30 |
| 3 | Learning problem | 25 seconds | 0:30–0:55 |
| 4 | Planned sources | 20 seconds | 0:55–1:15 |
| 5 | Proposed pipeline | 25 seconds | 1:15–1:40 |
| 6 | Raw JSON and HTML | 35 seconds | 1:40–2:15 |
| 7 | Collected and analyzed data | 35 seconds | 2:15–2:50 |
| 8 | MAE on real test listings | 40 seconds | 2:50–3:30 |
| 9 | Model selection | 40 seconds | 3:30–4:10 |
| 10 | Actual web interface | 30 seconds | 4:10–4:40 |
| 11 | Market dashboard | 20 seconds | 4:40–5:00 |

Use the timings as a rehearsal guide and shorten the spoken examples as needed. Rehearse at a comfortable pace and use the remaining pauses to point at the diagrams. There are no appendix slides or live-crawl steps.

## Slide 1 — Project introduction

Hello everyone. Our capstone is Hanoi Rent Insight, a proposed tool for estimating monthly asking rents for apartments and rental rooms in Hanoi. Today, we will summarize our objective, data approach, pipeline and actual web interface.

## Slide 2 — Objective

Renters often compare many listings whose locations, sizes and layouts differ. Landlords face a similar problem when choosing an initial asking price. Our objective is to provide a useful rent reference from property information, together with its limitations. We focus on apartments and rental rooms, and the target is advertised rent rather than signed-contract prices.

## Slide 3 — Learning problem

Following Tom Mitchell, we define three elements. Task: predict monthly asking rents for unseen Hanoi apartments and rental rooms. Performance: mean absolute error on held-out listings, compared with a median-rent baseline. Lower error means better performance. Experience: cleaned training listings from Nhatot and Alonhadat, pairing property features with advertised rents. This is supervised regression because the training examples have rent labels and the prediction is a continuous value. We will test whether learning improves performance.

## Slide 4 — Planned sources

Our planned sources are Nhatot and Alonhadat. We intend to collect listing JSON from one source and parse listing pages from the other, then map both into a shared schema. We will preserve IDs, URLs and dates for traceability. Pagination should include early-month listings, but deleted ads and blocked pages mean that a requested date range does not guarantee complete coverage.

## Slide 5 — Proposed pipeline

The pipeline starts with collection and raw storage. Next, we clean the data, explore its structure and prepare features. Candidate models are then trained and evaluated before one is connected to the web application. We also plan a monthly GitHub Actions workflow to repeat this process for the completed month. A model update should depend on quality checks; if a candidate fails, the currently accepted model should remain in service.

## Slide 6 — Actual raw JSON and HTML

The source-code excerpts show fields from our saved crawl on 30 October 2026. On the left, Nhatot returns JSON for listing 135562204: the title says Studio, the price is 6.5 million VND per month, the area is 30 square metres, and the source reports one bedroom. On the right, the Alonhadat HTML for listing 19180666 contains a numeric price of 18 million VND, an area of 116 square metres, and three bedrooms. We select only a few fields for readability; Location fields are also retained: street, ward, district and city in the JSON, and the address tags in the HTML. Full source snapshots accompany the presentation.

## Slide 7 — CSV before and after analysis

We follow the same two listing IDs into the CSV files. The first block is listings.csv, after extraction and structural normalization. The second is listings_analysis.csv, after analysis. For the Nhatot Studio, the source bedroom count changes from one to zero separate bedrooms based on the title; the original value remains preserved. Furnishing changes from the Vietnamese label to Furnished. For the Alonhadat listing, rent, area and bedroom count remain the same, while an empty furnishing field becomes Unknown. The tables show the saved CSV values; a dash represents an empty furnishing cell and the source rent string is spaced for readability. The accompanying record extracts preserve all columns, including the evidence fields.

## Slide 8 — MAE on three real test listings

These are saved predictions for three actual internal-test listings. For the first listing, the advertised rent is 15 million VND per month and the prediction is about 12.649 million, so the absolute error is 2.351 million. The other two absolute errors are 2.330 and 2.978 million. Their average is approximately 2.553 million VND per month. Both overestimates and underestimates count positively. This number describes these three examples only; it is not the MAE for the whole test set. The original unrounded prediction rows are included with the slides.

## Slide 9 — Model selection

We compare candidates using the same five grouped folds. Each round trains on four parts and validates on the remaining part; potential reposts stay together. We rank candidates by MAE across all validation predictions. The deployable candidates are constrained Gradient Boosting and Random Forest models, followed by feature-set comparisons. For near-ties within one percent of the best MAE, we prefer fewer features. The candidate must reduce overall MAE by at least ten percent compared with the category-median baseline, without increasing either category's MAE by more than ten percent. Otherwise, we keep the baseline. We then lock the choice, fit on all development data and evaluate on the separate internal test. Serving-model promotion has additional checks.

## Slide 10 — Actual web interface

This is the actual web application running locally, with its Vietnamese interface. On the left, the user selects a property type and district, enters the area, and optionally provides separate bedrooms and furnishing. Here, we use a 50-square-metre apartment in Hai Ba Trung with two separate bedrooms. The connected prediction service returns the asking-rent reference shown on the right. The page also shows historical error and nearby-size listing context. This demonstrates the implemented interaction; one example does not establish overall model quality or completed production deployment.

## Slide 11 — Market dashboard

This is the application's market dashboard. It groups observed asking rents by district and property type, showing the median, the middle half of listings and the listing count. The side panel shows the source composition and date coverage. These summaries describe the collected data and help users put the rent estimate in context.

## Questions to prepare for

- **What exactly do you predict?** Monthly asking rent for a whole apartment or rental room in Hanoi, in VND.
- **Why exclude private houses?** They introduce a broader mix of residential and commercial uses; the initial scope is narrower.
- **What are T, P and E in this project?** T is monthly asking-rent prediction; P is held-out MAE; E is cleaned, labelled training listings. Learning should improve P on T through E; collecting more records alone does not prove improvement.
- **Why MAE rather than accuracy?** Rent is continuous. MAE measures the average absolute difference between predicted and advertised monthly rents, in VND/month.
- **How will you assess the model?** Compare against a simple baseline on the same held-out rows, preserve repost groups and report errors separately by property type.
- **Will all October listings be available?** We can only collect listings the sources still expose; record access failures and observed date coverage.
- **How will you prevent leakage?** Keep repost groups in the same split, fit preprocessing on training folds only, and exclude price per square metre because it contains the target. Held-out listings assess performance; their labels are not training experience.
- **Why not fill missing bedrooms with zero?** Zero is a known studio layout. Missing means the layout is unknown.
- **Is the web application complete?** The local application supports the demonstrated prediction flow. Final validation and deployment are outside this update.
- **Are the displayed prices predictions?** Slide 7 contains observed source prices. Slide 10 shows an actual model prediction from the local application, alongside historical error and listing context.

- **Why not simply choose the lowest test MAE?** The internal test is reserved for evaluation after selection. Comparing and tuning candidates on it would contaminate that evaluation.
- **Do all tried models compete for deployment?** No. Ridge and unconstrained Random Forest runs are diagnostic comparisons. Selection for deployment considers constrained boosting/forest models and their feature sets.
- **Are the selection and release gates the same?** No. The slide's 10% category tolerance is for candidate selection versus the baseline. Replacing the serving model uses additional registry checks.

## Source record references for slides 6–7

| Listing ID | Raw source | Result illustrated |
| --- | --- | --- |
| `nt_135562204` | `data-examples/nhatot-p1.json` | Studio bedroom count 1 → 0; Đầy đủ → Furnished |
| `alo_19180666` | `data-examples/alonhadat-p1.html` | Rent/area/bedrooms retained; empty furnishing → Unknown |

Source URLs are preserved in the complete CSV rows. `data-examples/provenance.json` records source paths and hashes. These are saved snapshots, not claims about current live page availability. `collected-records.csv` is parsed and normalized data; the JSON/HTML snapshots are the raw sources. `analysis-records.csv` and `sample-records.csv` contain the complete corresponding analysis rows.
