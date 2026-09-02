# Engineering Decisions

## Initial stack

- FastAPI and SQLAlchemy for a small, typed Python API.
- SQLite for a zero-service local demo with real persistence and aggregation.
- React and Vite for the user feed and administrator interface.
- Pandas, NumPy and scikit-learn for a CPU-friendly offline pipeline.
- Docker Compose plus native local commands for reproducibility.

## Delivery strategy

Build a real vertical slice before optional sophistication. The first slice must
connect processed MicroLens data, a learned score, an authenticated feed,
exposure/event persistence, dashboard aggregation and server-side operations.

## Deferred until the required loop is stable

- Redis caching and asynchronous training jobs
- Image, video or multimodal embeddings
- A complex two-stage neural architecture
- Paid cloud infrastructure

These features are useful only after the scored acceptance path is reliable.

## Data split and leakage policy

- Split interactions by global event time into approximately 80% train, 10%
  validation and 10% test partitions.
- Keep identical millisecond timestamps in one partition so strict ordering
  holds across train, validation and test.
- Tune on train/validation only. Refit on train plus validation once before the
  final test evaluation.
- Evaluate collaborative models only on users and items known at fit time, and
  report the excluded cold-start share as coverage.
- Source likes/views have no observation timestamp. They may be used as clearly
  labeled online popular/cold-start priors, but never in temporal offline model
  comparison. Offline popularity baselines use fitting interactions only.

The global cutoff models a real deployment time. It is deliberately stricter
than a random split and exposes cold-start cases for online fallback handling.
