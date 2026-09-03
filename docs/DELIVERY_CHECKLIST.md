# Delivery Checklist

This checklist mirrors the required submission items and is the release gate.

## Required artifacts

- [x] Source repository with at least three meaningful commits
- [x] Demo URL, or complete local URL and startup instructions
- [x] Frontend, backend, database and CPU/smoke startup commands
- [x] Reproducible MicroLens-50K data preparation scripts
- [x] Model configuration, consumable artifact and evaluation report
- [x] Three normal test users and one administrator seed account
- [x] Database schema and API documentation
- [x] System design and offline-to-online data-flow documentation
- [x] README and `.env.example` without real secrets
- [x] Honest completion, mock, risk and one-week iteration notes
- [ ] Three-to-five-minute demonstration video

## Functional acceptance

- [x] Time-based train/validation/test split has no future leakage
- [x] Learnable model is compared with popularity and random baselines
- [x] At least two offline recommendation metrics are reported
- [x] Personalized, popular and explore feeds are available
- [x] Two users receive demonstrably different personalized results
- [x] Pagination, deduplication, seen filtering and fallback work
- [x] Every response includes source, score, model version and request ID
- [x] Impression, click, like/favorite and not-interested events are stored
- [x] Request ID connects recommendation requests, exposures and events
- [x] A user action changes the profile or subsequent ranking
- [x] Dashboard metrics are calculated from stored requests and events
- [x] Dashboard shows active users, Feed shares and real popular content
- [x] Time filters, trend chart, request trace and CSV export work
- [x] Server-side boost, offline and restore operations affect feeds
- [x] Offline content cannot be returned by bypassing the frontend
- [x] Normal users cannot access other users' data or admin endpoints
- [ ] A clean environment can reproduce the core flow

## Demonstration sequence

1. Start the project and show the training/evaluation command.
2. Log in as two users and compare personalized feeds.
3. Generate events and show the resulting metric/profile change.
4. Boost content as admin and verify it in the target feed.
5. Take content offline and prove it disappears from every feed.
