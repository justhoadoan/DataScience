# Hanoi Rent Insight

A rental-price estimation app for Hanoi, built with FastAPI and React.

## Folder structure

| Folder | Purpose |
| --- | --- |
| `src/hanoi_rentals/ingestion/` | Fetch listings and normalize source formats. |
| `src/hanoi_rentals/analysis/` | Audit listings and generate exploratory reports. |
| `src/hanoi_rentals/features/` | Shared property-feature extraction and layout rules. |
| `src/hanoi_rentals/modeling/` | Train and evaluate models, check prediction behavior and generate model reports. |
| `src/hanoi_rentals/operations/` | Coordinate the pipeline, model registry and saved state. |
| `src/hanoi_rentals/serving/` | FastAPI application, request validation and prediction endpoints. |
| `frontend/src/` | React views, forms, API requests and styling. |
| `data/` | Files used by collection, analysis and training. |
| `artifacts/` | Saved model bundles and the active-model registry. |
| `reports/` | Generated reports and figures. |
| `scripts/` | Local startup and workflow utilities. |
| `config/` | Model promotion settings. |
| `deploy/` | Production containers, reverse proxy and deployment scripts. |
| `.github/workflows/` | Build, monthly pipeline and deployment automation. |
| `docs/` | Team documentation and plans. |

The command-line entry point is `src/hanoi_rentals/cli.py`. Shared repository paths are defined in `src/hanoi_rentals/paths.py`.

## Run locally

Use Python 3.12, Node.js 22.12 or later, and npm. Run commands from the repository root.

```bash
./scripts/run_local.sh
```

The script installs dependencies, builds the frontend and starts the application. It uses the saved model when the registry is present and runs training if the registry is missing.

Open the application at **http://127.0.0.1:8000** and the API documentation at **http://127.0.0.1:8000/docs**.

To use another port, run `PORT=8080 ./scripts/run_local.sh`.

### Temporal-model preview

After local setup, run a small collection and an isolated date-feature experiment:

```bash
.venv/bin/python -m hanoi_rentals.cli replay-observations
.venv/bin/python -m hanoi_rentals.cli crawl --since 2025-11-01 --until 2026-12-31 --max-pages 3
.venv/bin/python -m hanoi_rentals.cli train-temporal
.venv/bin/python -m hanoi_rentals.cli --root .work/temporal-preview serve --port 8001
```

Open **http://127.0.0.1:8001** when training reports `preview_ready`. This preview uses its own model registry. The regular app continues to use the approved model.

Use `temporal-coverage` for the collection report. Run `evaluate-temporal-holdout` after December 2026 to evaluate the candidate frozen before December; earlier runs return `pending`.

### Crawl and resume

A new crawl downloads fresh responses. Omit `--max-pages` to traverse all accessible pages:

```bash
.venv/bin/python -m hanoi_rentals.cli crawl --since 2025-11-01 --until 2026-11-30
.venv/bin/python -m hanoi_rentals.cli backfill-archives --since 2025-11-01 --until 2026-11-30
```

To continue an interrupted crawl, use its printed run ID and the same date/source/category options. Keep that run's local raw responses available:

```bash
.venv/bin/python -m hanoi_rentals.cli crawl --since 2025-11-01 --until 2026-11-30 --resume RUN_ID
```

Use `--sources nhatot` or `--categories nha_tro` to select a source or category. A verification challenge stops requests to that source and is reported as incomplete collection.

### Phongtro123

Fetch the public Hanoi apartment and room listings with:

```bash
.venv/bin/python -m hanoi_rentals.cli crawl --sources phongtro123 --since 2025-11-01 --until 2026-11-30
```

For a targeted crawl, use `--categories`, `--start-page` and `--max-pages`. For example, these options select seven room listing pages starting at page 52:

```bash
.venv/bin/python -m hanoi_rentals.cli crawl --sources phongtro123 --categories nha_tro --since 2025-11-01 --until 2025-11-30 --start-page 52 --max-pages 7
```

Page numbers may shift as listings change. The date window filters the displayed listing date, and prices are dated to the day the page was downloaded in Hanoi. To resume a targeted crawl, reuse the starting page along with the source, category, and date options.

### Manual setup

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python -m hanoi_rentals.cli serve
```

### Frontend development

Start the backend in one terminal.

```bash
.venv/bin/python -m hanoi_rentals.cli serve
```

Start Vite in another terminal after installing the frontend dependencies.

```bash
cd frontend
npm run dev
```

Open the address printed by Vite. Requests to `/api` are forwarded to the backend on port 8000.

### Docker

```bash
docker compose up --build
```

Open **http://127.0.0.1:8000**. Stop the containers with `docker compose down`.
