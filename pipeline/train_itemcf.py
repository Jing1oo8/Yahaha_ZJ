"""Train and evaluate a CPU-friendly ItemCF recommender."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from prepare_data import Interaction


DEFAULT_K = 20
DEFAULT_NEIGHBORS = 100
DEFAULT_SEED = 20260902


@dataclass
class ItemCFModel:
    histories: dict[int, list[int]]
    neighbors: dict[int, list[tuple[int, float]]]
    popular_items: list[int]
    item_universe: list[int]


def read_interactions(path: Path) -> list[Interaction]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [
            Interaction(
                timestamp=int(row["timestamp"]),
                user=int(row["user"]),
                item=int(row["item"]),
            )
            for row in csv.DictReader(handle)
        ]


def build_model(events: Iterable[Interaction], neighbor_limit: int) -> ItemCFModel:
    user_items: dict[int, list[int]] = defaultdict(list)
    item_frequency: Counter[int] = Counter()
    for event in events:
        user_items[event.user].append(event.item)
        item_frequency[event.item] += 1

    cooccurrence: dict[int, Counter[int]] = defaultdict(Counter)
    for items in user_items.values():
        unique_items = sorted(set(items))
        if len(unique_items) < 2:
            continue
        contribution = 1.0 / math.log1p(len(unique_items))
        for left_index, left in enumerate(unique_items):
            for right in unique_items[left_index + 1 :]:
                cooccurrence[left][right] += contribution
                cooccurrence[right][left] += contribution

    neighbors: dict[int, list[tuple[int, float]]] = {}
    for item, related in cooccurrence.items():
        scored = [
            (other, count / math.sqrt(item_frequency[item] * item_frequency[other]))
            for other, count in related.items()
        ]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        neighbors[item] = scored[:neighbor_limit]

    histories = {
        user: [event_item for event_item in items]
        for user, items in user_items.items()
    }
    popular_items = [
        item for item, _ in sorted(item_frequency.items(), key=lambda pair: (-pair[1], pair[0]))
    ]
    return ItemCFModel(
        histories=histories,
        neighbors=neighbors,
        popular_items=popular_items,
        item_universe=sorted(item_frequency),
    )


def append_fallback(
    ranked: list[int], seen: set[int], fallback: Iterable[int], k: int
) -> list[int]:
    selected = set(ranked)
    for item in fallback:
        if item not in seen and item not in selected:
            ranked.append(item)
            selected.add(item)
            if len(ranked) == k:
                break
    return ranked


def recommend_itemcf(model: ItemCFModel, user: int, k: int) -> list[int]:
    history = model.histories.get(user, [])
    seen = set(history)
    scores: Counter[int] = Counter()
    for history_item in history:
        for candidate, similarity in model.neighbors.get(history_item, []):
            if candidate not in seen:
                scores[candidate] += similarity
    ranked = [item for item, _ in sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))[:k]]
    return append_fallback(ranked, seen, model.popular_items, k)


def recommend_popular(model: ItemCFModel, user: int, k: int) -> list[int]:
    return append_fallback([], set(model.histories.get(user, [])), model.popular_items, k)


def recommend_random(model: ItemCFModel, user: int, k: int, seed: int) -> list[int]:
    seen = set(model.histories.get(user, []))
    generator = random.Random((seed << 32) ^ user)
    ranked: list[int] = []
    selected: set[int] = set()
    while len(ranked) < k and len(selected) + len(seen) < len(model.item_universe):
        item = model.item_universe[generator.randrange(len(model.item_universe))]
        if item not in seen and item not in selected:
            selected.add(item)
            ranked.append(item)
    return ranked


def group_ground_truth(events: Iterable[Interaction]) -> dict[int, set[int]]:
    truth: dict[int, set[int]] = defaultdict(set)
    for event in events:
        truth[event.user].add(event.item)
    return truth


def user_metrics(recommendations: list[int], relevant: set[int], k: int) -> tuple[float, float, float]:
    hits = [1 if item in relevant else 0 for item in recommendations[:k]]
    recall = sum(hits) / len(relevant)
    hit_rate = 1.0 if any(hits) else 0.0
    dcg = sum(hit / math.log2(rank + 2) for rank, hit in enumerate(hits))
    ideal_hits = min(len(relevant), k)
    ideal_dcg = sum(1.0 / math.log2(rank + 2) for rank in range(ideal_hits))
    ndcg = dcg / ideal_dcg if ideal_dcg else 0.0
    return recall, hit_rate, ndcg


def evaluate(model: ItemCFModel, events: Iterable[Interaction], k: int, seed: int) -> dict[str, object]:
    truth = group_ground_truth(events)
    totals = {
        name: {"recall": 0.0, "hit_rate": 0.0, "ndcg": 0.0, "items": set()}
        for name in ("itemcf", "popularity", "random")
    }
    badcases: list[dict[str, object]] = []

    for user in sorted(truth):
        recommendations = {
            "itemcf": recommend_itemcf(model, user, k),
            "popularity": recommend_popular(model, user, k),
            "random": recommend_random(model, user, k, seed),
        }
        for name, ranked in recommendations.items():
            recall, hit_rate, ndcg = user_metrics(ranked, truth[user], k)
            totals[name]["recall"] += recall
            totals[name]["hit_rate"] += hit_rate
            totals[name]["ndcg"] += ndcg
            totals[name]["items"].update(ranked)
        if len(badcases) < 5 and not truth[user].intersection(recommendations["itemcf"]):
            badcases.append(
                {
                    "user": user,
                    "history_size": len(model.histories.get(user, [])),
                    "relevant_items": sorted(truth[user]),
                    "itemcf_top_k": recommendations["itemcf"],
                }
            )

    user_count = len(truth)
    metrics: dict[str, object] = {}
    for name, values in totals.items():
        metrics[name] = {
            f"recall@{k}": round(values["recall"] / user_count, 6),
            f"hit_rate@{k}": round(values["hit_rate"] / user_count, 6),
            f"ndcg@{k}": round(values["ndcg"] / user_count, 6),
            f"catalog_coverage@{k}": round(
                len(values["items"]) / len(model.item_universe), 6
            ),
        }
    return {"users": user_count, "metrics": metrics, "itemcf_badcases": badcases}


def model_version(manifest: dict[str, object], stage: str, neighbor_limit: int) -> str:
    identity = json.dumps(
        {
            "raw_files": manifest["raw_files"],
            "boundaries": manifest["boundaries"],
            "stage": stage,
            "algorithm": "itemcf-iuf-cosine",
            "neighbor_limit": neighbor_limit,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return f"itemcf-{hashlib.sha256(identity).hexdigest()[:12]}"


def export_model(path: Path, model: ItemCFModel, metadata: dict[str, object]) -> None:
    payload = {
        "metadata": metadata,
        "popular_items": model.popular_items,
        "neighbors": {
            str(item): [[other, round(score, 8)] for other, score in related]
            for item, related in sorted(model.neighbors.items())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    with path.open("wb") as raw_handle:
        with gzip.GzipFile(fileobj=raw_handle, mode="wb", mtime=0) as handle:
            handle.write(encoded)


def load_model_artifact(path: Path) -> dict[str, object]:
    """Load the versioned artifact through the same format used by serving."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not {"metadata", "popular_items", "neighbors"}.issubset(payload):
        raise ValueError("ItemCF artifact is missing required fields")
    return payload


def train(
    processed_dir: Path,
    models_dir: Path,
    report_path: Path,
    stage: str,
    k: int,
    neighbor_limit: int,
    seed: int,
) -> dict[str, object]:
    manifest = json.loads((processed_dir / "split_manifest.json").read_text(encoding="utf-8"))
    if stage == "validation":
        fit_files = ["train.csv"]
        evaluation_file = "validation_eval.csv"
    else:
        fit_files = ["train.csv", "validation.csv"]
        evaluation_file = "test_eval.csv"

    fit_events = [
        event
        for filename in fit_files
        for event in read_interactions(processed_dir / filename)
    ]
    evaluation_events = read_interactions(processed_dir / evaluation_file)
    model = build_model(fit_events, neighbor_limit)
    version = model_version(manifest, stage, neighbor_limit)
    evaluation = evaluate(model, evaluation_events, k, seed)
    metadata = {
        "model_version": version,
        "algorithm": "itemcf-iuf-cosine",
        "stage": stage,
        "fit_files": fit_files,
        "evaluation_file": evaluation_file,
        "fit_interactions": len(fit_events),
        "fit_users": len(model.histories),
        "fit_items": len(model.item_universe),
        "neighbor_limit": neighbor_limit,
        "k": k,
        "seed": seed,
    }
    artifact_path = models_dir / f"{version}.json.gz"
    export_model(artifact_path, model, metadata)
    report = {
        **metadata,
        "artifact": artifact_path.as_posix(),
        "evaluation": evaluation,
        "metric_protocol": {
            "unit": "macro average over users with at least one scoreable future event",
            "seen_filter": "exclude fitting-history items",
            "itemcf": "IUF-weighted co-occurrence with cosine normalization and popularity fallback",
            "popularity": "interaction counts from fitting files only",
            "random": "deterministic unseen-item sample",
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    parser.add_argument("--report", type=Path, default=Path("data/artifacts/evaluation.json"))
    parser.add_argument("--stage", choices=("validation", "final"), default="validation")
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--neighbors", type=int, default=DEFAULT_NEIGHBORS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = train(
        processed_dir=args.processed_dir,
        models_dir=args.models_dir,
        report_path=args.report,
        stage=args.stage,
        k=args.k,
        neighbor_limit=args.neighbors,
        seed=args.seed,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
