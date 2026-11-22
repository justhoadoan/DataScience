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
