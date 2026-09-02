# System Design

## Architecture

```text
MicroLens raw files
        |
        v
inspect_raw.py -> raw audit (hashes, quality, statistics)
        |
        v
prepare_data.py -> temporal CSVs + item catalog + user histories + manifest
        |
        v
train_itemcf.py -> validation/test reports + versioned ItemCF gzip artifact
        |
        +------------------------+
        v                        v
FastAPI recommendation API <-> SQLite <-> Dashboard and Content Ops
        ^                        |
        |                        v
React Feed <- request/exposure/event/profile feedback loop
```

The model publish boundary is the versioned gzip artifact plus its model-version
row. A failed training run writes a separate report/artifact and never overwrites
the published version. Online service startup loads the configured `MODEL_PATH`;
if unavailable, it reports `model_available=false` and can fall back to popular
content instead of returning a hard-coded personalized list.

## Recall, ranking, and mixing

- Personalized: sum learned ItemCF neighbor similarities from offline history and
  online likes/favorites; remove history, exposures, and not-interested items.
- Popular: rank online content by source views then likes. These are explicitly
  online catalog priors and were excluded from temporal offline evaluation.
- Explore: rank unseen content by global exposure count, then a deterministic
  user-item hash for stable diversity.
- Fallback: personalized candidate shortages use fit-window interaction popularity.
- Operator boost: active rules are inserted after algorithmic ranking but before
  pagination. Rules can target user/feed and carry reason, priority, and time range.
- Offline filter: applied before and after operations through server-owned item
  state. Offline content cannot be fetched directly or returned by boosts.

All feeds support cursor-style integer offsets, deduplication, seen filtering,
and explicit empty/error/loading UI states. Each returned item retains source,
score, model version, position, and request ID for diagnosis.

## Online feedback

Feed requests synchronously persist request and exposure rows plus impressions.
Click/like/favorite/not-interested calls must match an owned exposure and use a
unique client event ID. Likes/favorites join the next ItemCF history immediately;
not-interested items join the exclusion set. Offline retraining can later append
validated events to a new training snapshot without mutating old evaluation data.

Duplicate events are ignored by unique event ID. Out-of-order events are safe
because ranking uses event type and stored timestamp rather than arrival order.
Events referencing absent metadata are rejected because exposure and item foreign
keys must already exist.

## Permissions and failure recovery

- Session and role checks are server-side on every protected request.
- A user can only submit events against their own exposures and profile endpoint.
- Admin status changes and boosts are audited with actor, item, before/after state,
  reason, and timestamp.
- Offline wins over boost. Restore only returns content to normal candidate logic.
- SQLite is sufficient for the local MVP. A production evolution would move to
  PostgreSQL, cache model candidates in Redis, and process events asynchronously.
- Generated data, databases, and models are ignored; raw files and secrets never
  enter Git.

## Known limits

- ItemCF has weak relevance for one-interaction users and unseen items.
- Integer-offset pagination can shift when operations change during a session; a
  production stable cursor would encode candidate snapshot/version and last score.
- Dashboard currently shows aggregate totals rather than a time-series comparison.
- Source statistics have unknown observation time and are never used in offline
  temporal evaluation.
