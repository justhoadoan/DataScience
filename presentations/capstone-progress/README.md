# Hanoi Rent Insight — capstone progress slides

**11 slides; data slide headings and labels in English.** The deck covers the objective, learning problem, sources, pipeline, actual JSON/HTML excerpts, matching CSV rows before and after analysis, a real-data MAE calculation, model selection, the local web interface and the market dashboard.

This is a progress presentation. It deliberately focuses on scope, sample work and proposed integration; it does not treat the displayed example or historical error as final model validation, claim full monthly data coverage or present production deployment as complete.

## Open or edit

- `progress-report.pdf`: compiled presentation.
- `progress-report.tex`: main editable Beamer document.
- `metadata.tex`: title, five team members with student IDs, advisor and date.
- `speaker-notes.md`: English script with timings totalling exactly 300 seconds.
- `sample-records.csv`: the two complete analysis rows used on slides 6–7, copied from `data/analysis/listings_analysis.csv`.
- `data-examples/`: original JSON/HTML snapshots, exact record extracts, collected/analysis CSV rows, slide excerpts and source provenance.
- `capstone-progress-overleaf.zip`: self-contained editable Overleaf package.

## Compile on Overleaf

Upload `capstone-progress-overleaf.zip` as a new project. Select `progress-report.tex` as the main document and **XeLaTeX** as the compiler, then recompile. No files outside the package are required.

## Compile locally

Run `sh build.sh` from this directory. The script uses XeLaTeX, optionally via latexmk, and writes `progress-report.pdf`. Compiler intermediates are stored in `build/`.

## Template and data provenance

The HUST red 16:9 theme, Latin Modern Sans setup, header layout and title treatment come from the sibling `week2_overleaf` directory (`../../../week2_overleaf` relative to this folder). `beamerthemeHUST.sty` and the two used background images are copied unchanged. The theme's original author attribution remains in its header. The English project-team label is a document-level patch. Slide numbers are hidden. The cover follows the Week 2 layout: the original large title, left-aligned subtitle and project-team label, one name–student ID per line, and a black lecturer line beneath. It keeps all five team members and displays “Lecturer: Assoc. Prof. Dr. Than Quang Khoat”; the date is omitted from the cover to match the template.

Slides 6–7 follow two actual listings through the saved raw sources and the CSV pipeline:

- Nhatot `nt_135562204`: JSON lists a Studio at 6.5 million VND/month, 30 m², and one bedroom. The collected CSV retains one bedroom; analysis records zero separate bedrooms with `bedrooms_origin=title_explicit`, and maps “Đầy đủ” to `Furnished`.
- Alonhadat `alo_19180666`: HTML contains 18 million VND/month, 116 m² and three bedrooms. Those values are retained; empty furnishing becomes `Unknown`.

Raw snapshots are from `data/raw/2026-10-30/`. `data-examples/provenance.json` records original paths and SHA-256 hashes. The `*-p1` files are byte-for-byte source copies. Slide 6 displays the JSON and HTML excerpts as source code, with English headings. Slide 7 displays the collected and analysis CSV values in two tables, marking an empty CSV cell with a dash. The exact JSON, HTML and CSV extracts remain in `data-examples/` for inspection. `collected-records.csv` and `analysis-records.csv` retain every column of the two selected rows from `data/processed/listings.csv` and `data/analysis/listings_analysis.csv`, respectively. The collected CSV has already been parsed and structurally normalized; it is not the raw HTTP response.

Slide 10 uses `images/web-estimator.png`, captured from the actual React/FastAPI application running locally on 2 November 2026. The Vietnamese UI shows a real prediction for a 50-square-metre apartment in Hai Ba Trung with two separate bedrooms and unknown furnishing. The screenshot demonstrates the local prediction flow; it does not establish overall model quality or completed production deployment.

Slide 9 summarizes the selection logic in `src/hanoi_rentals/modeling.py`: five grouped validation folds; constrained boosting/forest candidate search; feature-set comparison with a 1% tie band preferring fewer features; at least 10% overall MAE improvement over the category-median baseline and no category MAE more than 10% worse than baseline. If the candidate fails, the baseline is selected. The locked choice is fitted on the development set and evaluated on the separate internal test. Ridge and unconstrained forests are diagnostic comparisons; promotion to the serving registry is a separate gate.

The raw JSON example includes street, ward, district and city; the HTML example includes the original address tags. The collected/analysis tables include the district. Code wrapping adds no arrow characters to the displayed source.

Slide 8 demonstrates MAE using the first three `ablation_C` / `internal_test` rows in the saved `reports/modeling_predictions.csv` file, without selecting by error size. Full prediction rows are preserved in `data-examples/mae-example.csv`. Amounts on the slide are in million VND/month and rounded to three decimals. The unrounded mean absolute error of these three rows is 2,553,047.4230754436 VND/month; this is an illustrative subset, not the complete test-set MAE.

Slide 11 uses `images/web-dashboard.png`, captured from the actual local application's market view on 4 November 2026. It shows district rent summaries and source counts for the saved data snapshot.

## Validation

The PDF was compiled with XeLaTeX and checked as an eleven-page, 16:9 deck. The revised data slides, cover and model-selection slide were visually reviewed; the final compiler log has no overfull/underfull boxes or missing-character/font warnings. The Overleaf source package was also compiled in a separate temporary directory.
