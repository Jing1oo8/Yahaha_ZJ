# Offline Model Evaluation

## Model and baselines

The required learnable baseline is ItemCF. It learns item-item similarity from
fit-window user co-occurrence, discounts large user baskets with inverse user
frequency, and cosine-normalizes by item frequency. For a user, neighbors of
historical items are summed, seen items are removed, and fit-window popularity
fills a short candidate list.

It is compared with fitting-window popularity and a seeded deterministic random
sample of unseen items. Source likes/views are excluded from offline comparison
because their observation times are unknown. They remain available as a clearly
labeled online cold-start prior.

## Commands

First create processed data as described in `docs/DATA.md`. Then run validation:

```powershell
python pipeline/train_itemcf.py `
  --stage validation `
  --report data/artifacts/validation_evaluation.json
```

After fixing the configuration from validation, run the final refit and test once:

```powershell
python pipeline/train_itemcf.py `
  --stage final `
  --report data/artifacts/final_evaluation.json
```

Both commands are CPU-only. On the development machine, the final command fit
323,737 interactions and evaluated three recommenders for 11,774 users in
148.9 seconds. Allow at least 2 GB of free memory. The final compressed model is
about 8 MB.

## Evaluation protocol

- Configuration: `neighbor_limit=100`, `K=20`, random seed `20260902`.
- Validation fit: `train.csv`; evaluation: `validation_eval.csv`.
- Final fit: `train.csv + validation.csv`; evaluation: `test_eval.csv`.
- Unit: macro average over users with at least one scoreable future event.
- Relevant set: all scoreable future items for that user in the evaluation window.
- Seen items from the fit history are removed from every recommender.
- Recall@20 measures the fraction of relevant future items retrieved.
- HitRate@20 measures the fraction of users with at least one hit.
- NDCG@20 rewards hits more when they appear near the top.
- Catalog coverage is unique recommended items divided by fitting-catalog items.

## Results

### Validation

| Recommender | Recall@20 | HitRate@20 | NDCG@20 | Catalog coverage@20 |
| --- | ---: | ---: | ---: | ---: |
| ItemCF | 0.051297 | 0.060626 | 0.021676 | 1.000000 |
| Popularity | 0.004870 | 0.005626 | 0.001688 | 0.002543 |
| Random | 0.000787 | 0.001176 | 0.000275 | 1.000000 |

### Final test

| Recommender | Recall@20 | HitRate@20 | NDCG@20 | Catalog coverage@20 |
| --- | ---: | ---: | ---: | ---: |
| ItemCF | 0.044269 | 0.053508 | 0.017938 | 1.000000 |
| Popularity | 0.005016 | 0.006370 | 0.001384 | 0.002196 |
| Random | 0.000719 | 0.001104 | 0.000299 | 1.000000 |

The learned model beats both baselines on all three ranking metrics. The modest
absolute values are credible for sparse implicit data, a strict global temporal
cutoff, and only ID co-occurrence features. The validation-to-test drop indicates
time drift; the test set was not reused for another tuning round.

Catalog coverage for ItemCF and random reaches the fitting catalog across all
users, while popularity concentrates on very few items. Coverage does not imply
quality by itself: random has high coverage and very low relevance, so relevance
and coverage must be read together.

## Badcase analysis

The sampled zero-hit ItemCF cases consistently have only one fit-history item.
One interaction provides too little co-occurrence evidence, and future items may
not be neighbors of that single item. This motivates the required online design:

1. Fall back to popular and explore feeds for short-history and cold users.
2. Add title/content recall later, especially for cold items.
3. Update the online profile immediately after like/not-interested behavior.
4. Preserve source and score fields so Dashboard can diagnose each recall path.

## Consumable artifact

The final version is `itemcf-0022f60b5e4b`, written to
`models/itemcf-0022f60b5e4b.json.gz`. Its deterministic version derives from raw
hashes, split boundaries, stage, algorithm, and neighbor configuration. The gzip
JSON contains metadata, fit-only popular items, and top item neighbors. User
histories are stored in `data/processed/user_history.jsonl`.

`load_model_artifact()` validates and loads the same format intended for the
online service. Generated artifacts remain ignored by Git and are rebuilt with
the documented command.
