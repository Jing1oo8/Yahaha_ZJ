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

