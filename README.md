# YAHAHA Recommendation System MVP

A two-day recommendation-system engineering exercise based on MicroLens-50K.

The target is a reproducible end-to-end loop:

```text
MicroLens data -> offline training -> recommendation API -> user events
      -> observable metrics -> content operations -> updated feed
```

## Project status

The repository skeleton and delivery guardrails are initialized. Implementation
will proceed in vertical slices so every milestone remains runnable.

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

Detailed setup and run commands will be added as each runnable component lands.

