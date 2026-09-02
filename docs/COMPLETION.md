# Completion and AI Collaboration

## Completed

- Audited three official MicroLens-50K files with hashes and quality statistics.
- Reproducible global temporal train/validation/test processing with cold coverage.
- CPU ItemCF with popularity/random baselines, three metrics, Badcase analysis,
  deterministic version, gzip export and serving loader.
- Four seeded accounts, PBKDF2 passwords, server sessions and role authorization.
- Personalized, popular and explore Feed with pagination, source, score, model
  version, request ID, deduplication, seen filtering and fallback.
- Request, exposure, impression, click, like/favorite and not-interested storage;
  idempotency and exposure ownership validation; immediate profile feedback.
- Database-driven Dashboard, content search, timed boost, offline and restore;
  offline state is enforced by Feed, boost and direct item APIs.
- React UI, OpenAPI, system/data/evaluation documentation, integration tests and
  verified production frontend build.

## Not completed or intentionally deferred

- Public cloud Demo URL and 3-5 minute video are not created in the repository.
- Dashboard time-range charts, CSV export and model-version comparison are bonus
  features and remain deferred.
- DSSM plus DeepFM/MLP, negative sampling and multimodal features are bonus work;
  the required learnable model is the explainable ItemCF baseline.
- Docker Compose, Redis, asynchronous training, CI and structured latency metrics
  are deferred until the local scored path is stable.
- Placeholder covers are used; original videos are not loaded, as allowed.

No required core endpoint uses fixed recommendation JSON or fixed Dashboard
metrics. Seeded credentials and MicroLens user mapping are demonstration data;
recommendations, requests, exposures, behavior, metrics and operations are real.

## Largest current risk

Strict global time splitting leaves only about 45% of validation/test events
scoreable by collaborative filtering, and one-interaction users dominate sampled
zero-hit cases. Online fallback exists, but relevance for cold users/items is the
largest modeling risk. A title-based content recall source is the next highest
value improvement.

## One-week iteration

1. Add TF-IDF/title embedding recall and compare hybrid metrics by history length.
2. Snapshot stable cursors and expose filter/reason traces per request.
3. Add Dashboard time filters, trend charts, model comparison and CSV export.
4. Append validated online events to a versioned training snapshot and schedule
   asynchronous retraining with publish/rollback checks.
5. Add Docker Compose, CI, structured logs, latency percentiles and failure alerts.
6. Run usability testing, record the required demo video, and deploy a temporary
   public Demo with restricted test credentials.

## AI collaboration record

OpenAI Codex was used for repository inspection, implementation, tests, browser
verification and documentation. Key prompts from the candidate asked Codex to:

- inherit `README.md`, `docs/DECISIONS.md` and the delivery checklist;
- inspect MicroLens fields, rows, hashes, missing values and statistics;
- design a leakage-safe temporal pipeline and explain it step by step;
- follow the live Feishu assignment requirements while implementing and verifying.

AI contributed most initial code and documentation drafts. Human review decisions
included retaining an explainable ItemCF MVP, enforcing a strict global cutoff,
keeping raw data out of Git, and requiring live Feishu requirement verification.
During review, the source likes/views policy was corrected: allowed as a labeled
online popular prior, forbidden in temporal offline comparison. Tool failures were
not treated as successful verification; full runs and browser checks were repeated.

Verification performed: raw audit, full data processing, validation and final
model evaluation, 9 Python tests, frontend production build, desktop/mobile visual
inspection, real Alice login/feed/like/profile flow, and admin Dashboard inspection.
