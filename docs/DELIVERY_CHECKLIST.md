# Delivery Checklist

This checklist mirrors the required submission items and is the release gate.

## Required artifacts

- [ ] Source repository with at least three meaningful commits
- [ ] Demo URL, or complete local URL and startup instructions
- [ ] Frontend, backend, database and CPU/smoke startup commands
- [ ] Reproducible MicroLens-50K data preparation scripts
- [ ] Model configuration, consumable artifact and evaluation report
- [ ] Three normal test users and one administrator seed account
- [ ] Database schema and API documentation
- [ ] System design and offline-to-online data-flow documentation
- [ ] README and `.env.example` without real secrets
- [ ] Honest completion, mock, risk and one-week iteration notes
- [ ] Three-to-five-minute demonstration video

## Functional acceptance

- [ ] Time-based train/validation/test split has no future leakage
- [ ] Learnable model is compared with popularity and random baselines
- [ ] At least two offline recommendation metrics are reported
- [ ] Personalized, popular and explore feeds are available
- [ ] Two users receive demonstrably different personalized results
- [ ] Pagination, deduplication, seen filtering and fallback work
- [ ] Every response includes source, score, model version and request ID
- [ ] Impression, click, like/favorite and not-interested events are stored
- [ ] Request ID connects recommendation requests, exposures and events
- [ ] A user action changes the profile or subsequent ranking
- [ ] Dashboard metrics are calculated from stored requests and events
- [ ] Server-side boost, offline and restore operations affect feeds
- [ ] Offline content cannot be returned by bypassing the frontend
- [ ] Normal users cannot access other users' data or admin endpoints
- [ ] A clean environment can reproduce the core flow

## Demonstration sequence

1. Start the project and show the training/evaluation command.
2. Log in as two users and compare personalized feeds.
3. Generate events and show the resulting metric/profile change.
4. Boost content as admin and verify it in the target feed.
5. Take content offline and prove it disappears from every feed.

