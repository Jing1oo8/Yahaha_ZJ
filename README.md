# YAHAHA Recommendation System MVP

A two-day recommendation-system engineering exercise based on MicroLens-50K.

The target is a reproducible end-to-end loop:

```text
MicroLens data -> offline training -> recommendation API -> user events
      -> observable metrics -> content operations -> updated feed
```

## Project status

The CPU-only data, ItemCF, FastAPI/SQLite, React Feed, feedback, Dashboard and
content-operations loop is runnable locally. Generated data, databases and model
artifacts remain ignored by Git.

## Repository layout

```text
backend/             FastAPI application, database, auth and online serving
frontend/            React user feed, dashboard and content operations UI
pipeline/            Data preparation, training, evaluation and model export
tests/               Integration and end-to-end tests
docs/                Design, API, evaluation and delivery documentation
data/                 Local-only raw and processed data (ignored by Git)
models/               Local-only model artifacts (ignored by Git)
```

## Data policy

MicroLens files and generated model artifacts must remain local. The repository
contains scripts and documentation only; `.gitignore` excludes `data/raw/`,
`data/processed/`, `data/artifacts/`, and `models/`.

## Data audit and preparation

Place the three official MicroLens-50K files under `data/raw/`, then run:

```powershell
python pipeline/inspect_raw.py --output data/artifacts/raw_audit.json
python pipeline/prepare_data.py --output-dir data/processed
python -m unittest discover -s tests -v
```

The preparation command produces train/validation/test interactions, content
metadata, fit-time user histories, and a manifest with hashes and summary
statistics. It uses strict global time boundaries instead of randomly mixing
future interactions into training. See `docs/DATA.md` for the schema, measured
statistics, evaluation protocol and leakage rules.

## Offline ItemCF training

After data preparation, run validation and then the one-time final refit/test:

```powershell
python pipeline/train_itemcf.py --stage validation --report data/artifacts/validation_evaluation.json
python pipeline/train_itemcf.py --stage final --report data/artifacts/final_evaluation.json
```

This CPU-only pipeline learns ItemCF similarities, compares them with fitting-
window popularity and deterministic random baselines, and exports a gzip JSON
artifact for online serving. The measured full final run took 148.9 seconds;
allow at least 2 GB of free memory. See `docs/EVALUATION.md` for metric definitions,
actual results and badcase analysis.

## Local setup and startup

Prerequisites: Python 3.12+, Node.js 20+, and pnpm. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd frontend
pnpm install
cd ..
```

Place the three official MicroLens files in `data/raw/`, run the preparation and
final training commands above, then initialize SQLite:

```powershell
python -m backend.app.seed
```

Start the backend in terminal 1:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Start the frontend in terminal 2:

```powershell
cd frontend
pnpm run dev
```

Open `http://127.0.0.1:5173/`. OpenAPI documentation is at
`http://127.0.0.1:8000/docs`. The frontend uses Vite's local `/api` proxy, so no
cross-origin browser configuration is required.

## Test accounts

| Role | Username | Password | MicroLens identity |
| --- | --- | --- | ---: |
| User | `alice` | `alice123` | 1 |
| User | `bob` | `bob12345` | 2 |
| User | `carol` | `carol123` | 3 |
| Administrator | `admin` | `admin123` | none |

These are local demonstration credentials, not production secrets. Passwords are
stored as salted PBKDF2 hashes after seeding.

## Verification

```powershell
python -m unittest discover -s tests -v
cd frontend
pnpm run build
```

The integration test proves two-user personalization, event idempotency, profile
change, request/exposure linkage, admin authorization, server-side boost, offline
filtering through both Feed and direct item API, and restore behavior.

## Demo path

1. Run data preparation and show `split_manifest.json` summary.
2. Run final ItemCF evaluation and show the baseline table in `docs/EVALUATION.md`.
3. Log in as Alice and Bob and compare personalized Feed results.
4. Like/not-interested content and open Profile and Dashboard to show real changes.
5. In Dashboard, change the time range, inspect trends, Feed shares, popular
   content and a request trace, then export the linked events as CSV.
6. Log in as admin, boost an item, then offline it and verify it disappears.

Detailed contracts and tradeoffs are in `docs/API.md`, `docs/SYSTEM_DESIGN.md`,
`docs/DATA.md`, `docs/EVALUATION.md`, and `docs/COMPLETION.md`.
