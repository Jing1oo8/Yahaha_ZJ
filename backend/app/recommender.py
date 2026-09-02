from __future__ import annotations

import gzip
import json
import os
from collections import Counter
from pathlib import Path


class RecommenderRuntime:
    def __init__(self) -> None:
        model_path = Path(os.getenv("MODEL_PATH", "models/itemcf-0022f60b5e4b.json.gz"))
        history_path = Path(os.getenv("USER_HISTORY_PATH", "data/processed/user_history.jsonl"))
        self.available = model_path.is_file() and history_path.is_file()
        self.version = "popular-fallback"
        self.neighbors: dict[int, list[tuple[int, float]]] = {}
        self.popular_items: list[int] = []
        self.histories: dict[int, list[int]] = {}
        if not self.available:
            return

        with gzip.open(model_path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.version = payload["metadata"]["model_version"]
        self.popular_items = [int(item) for item in payload["popular_items"]]
        self.neighbors = {
            int(item): [(int(other), float(score)) for other, score in related]
            for item, related in payload["neighbors"].items()
        }
        with history_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                self.histories[int(record["user"])] = [int(item) for item in record["items"]]

    def history(self, dataset_user_id: int | None) -> list[int]:
        return list(self.histories.get(dataset_user_id or -1, []))

    def personalized(
        self,
        dataset_user_id: int | None,
        positive_items: list[int],
        excluded_items: set[int],
    ) -> list[tuple[int, float, str]]:
        history = [*self.history(dataset_user_id), *positive_items]
        seen = set(history) | excluded_items
        scores: Counter[int] = Counter()
        for item in history:
            for candidate, similarity in self.neighbors.get(item, []):
                if candidate not in seen:
                    scores[candidate] += similarity
        ranked = [
            (item, float(score), "itemcf")
            for item, score in sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
        ]
        selected = {item for item, _, _ in ranked}
        for rank, item in enumerate(self.popular_items):
            if item not in seen and item not in selected:
                ranked.append((item, 1.0 / (rank + 1), "popular_fallback"))
        return ranked


runtime = RecommenderRuntime()
