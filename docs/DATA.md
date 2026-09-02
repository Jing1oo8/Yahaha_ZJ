# MicroLens-50K Data

This document records the raw-data audit, field semantics, temporal split and
future-leakage rules. Raw and generated data remain local and are ignored by Git.

## Reproducible commands

Run from the repository root:

```powershell
python pipeline/inspect_raw.py --output data/artifacts/raw_audit.json
python pipeline/prepare_data.py --output-dir data/processed
python -m unittest discover -s tests -v
```

The first command only reads raw files. The second creates deterministic temporal
splits. JSON reports and generated CSV files are not committed.

## Raw files and hashes

These values were measured locally on 2026-09-02. SHA-256 identifies the exact
dataset version instead of relying on filenames.

| File | Bytes | Rows | SHA-256 |
| --- | ---: | ---: | --- |
| `MicroLens-50k_pairs.csv` | 9,431,093 | 359,708 | `7ff8b91bcc84f5434ac2c5be7d0b7d7730f5e84f79f9648b5ae67a7641f97bbd` |
| `MicroLens-50k_titles.csv` | 2,392,145 | 19,220 | `244aad5380cbbe0fb43458cfcda5ebe820f534384602f80a64dbbcd07dd30e49` |
| `MicroLens-50k_likes_and_views.txt` | 386,787 | 19,220 | `9031dcd6fd575abc28776b6fe55a9b5a5a6446ff1d25bbb97d0e9437f480dfb2` |

## Fields and statistics

`MicroLens-50k_pairs.csv` has `user`, `item`, and Unix-millisecond `timestamp`
columns. It contains 50,000 users, 19,220 items, and 359,708 implicit-positive
interactions from `2020-03-05T03:23:49.552Z` through
`2022-09-12T12:02:12.429Z`.

Interactions per user: min 5, median 6, P90 11, P95 13, max 218, mean 7.1942.
Interactions per item: min 1, median 11, P90 44, P95 59, max 342, mean 18.7153.
The sparse and skewed distribution motivates a popularity fallback, but the
learned model must still be compared with popularity and random baselines.

`MicroLens-50k_titles.csv` maps `item` to `title`. It contains 19,220 unique
items. Title lengths range from 4 to 6,293 characters (median 109, P95 205).
Titles may later support content features or cold-start explanations.

`MicroLens-50k_likes_and_views.txt` has no header and is tab-delimited in the
order `item`, `likes`, `views`. Likes range from 10,000 to 4,731,000 and views
from 44,000 to 93,373,000. No row has likes greater than views.

The likes/views file has no observation timestamps and may contain full-period
information. It must not enter temporal model features or offline baseline
comparisons. The online popular/cold-start feed may use it as an explicitly
labeled static catalog prior, which the assignment permits. The offline
popularity baseline must count interactions from its fitting partition only.

## Data-quality result

- No file has missing or invalid values.
- The interaction table has no exact duplicate or repeated `(user, item)` rows.
- The title and display-stat tables have no duplicate item keys.
- All three files contain exactly the same 19,220-item set.
- No raw row needs deletion. The preparation code still defensively retains the
  earliest event if a future dataset contains repeated user-item interactions.

## Leakage-safe temporal split

A random split would let future behavior influence training and inflate offline
metrics. The pipeline instead models a real deployment cutoff:

1. Sort by `(timestamp, user, item)` for deterministic output.
2. Select global timestamp boundaries near the 80% and 90% event positions.
3. Put events before the first boundary in train.
4. Put events from the first boundary up to the second in validation.
5. Put events at or after the second boundary in test.
6. Keep all events sharing a millisecond in one partition.

Global cutoffs are stricter than per-user holdouts and expose genuine cold-start
users/items. For validation, fit only on train and score `validation_eval.csv`.
After configuration selection, refit once on train plus validation and score
`test_eval.csv`. Eval files contain only users and items known at their fitting
cutoff. The excluded cold-start share is reported separately as coverage and is
handled online by popular, explore, and later content-based fallbacks.

The test set must not be inspected repeatedly during model selection.

### Measured split result

The full pipeline was run on 2026-09-02 with these actual boundaries and row
counts (not estimates):

| Partition | Rows | Users | Items | Time range (UTC) |
| --- | ---: | ---: | ---: | --- |
| Train | 287,766 | 49,416 | 16,907 | 2020-03-05 03:23:49 to 2022-08-26 14:27:57 |
| Validation | 35,971 | 21,612 | 5,929 | 2022-08-26 14:28:16 to 2022-09-04 00:45:37 |
| Test | 35,971 | 20,862 | 5,503 | 2022-09-04 00:46:18 to 2022-09-12 12:02:12 |
| Validation eval | 16,004 | 11,909 | 4,474 | within the validation window |
| Test eval | 16,499 | 11,774 | 4,403 | within the test window |

Validation collaborative-event coverage is `16,004 / 35,971 = 44.49%`.
Final test collaborative-event coverage is `16,499 / 35,971 = 45.87%`.
The remaining events contain a user or item unseen at the relevant fit cutoff.
They are retained in the complete windows for explicit cold-start analysis and
online fallback testing rather than being silently discarded.

## Generated files

`pipeline/prepare_data.py` writes these ignored files under `data/processed/`:

| File | Purpose |
| --- | --- |
| `train.csv` | Model fitting and train-only popularity baseline |
| `validation.csv` | Full validation window and final refit input |
| `validation_eval.csv` | Validation events scoreable by the train model |
| `test.csv` | Full final test window and coverage analysis |
| `test_eval.csv` | Final events scoreable after train+validation refit |
| `items.csv` | Titles and source likes/views with restricted offline use |
| `user_history.jsonl` | Chronological user history from train plus validation (49,887 users) |
| `split_manifest.json` | Raw hashes, boundaries, row counts, and feature policy |

The manifest connects every later model version and evaluation report to the
exact source files and split boundaries.
