from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from prepare_data import Interaction  # noqa: E402
from train_itemcf import (  # noqa: E402
    build_model,
    export_model,
    load_model_artifact,
    recommend_itemcf,
    recommend_random,
    user_metrics,
)


class ItemCFTest(unittest.TestCase):
    def setUp(self) -> None:
        self.events = [
            Interaction(timestamp=1, user=1, item=10),
            Interaction(timestamp=2, user=1, item=20),
            Interaction(timestamp=3, user=2, item=10),
            Interaction(timestamp=4, user=2, item=30),
            Interaction(timestamp=5, user=3, item=20),
            Interaction(timestamp=6, user=3, item=40),
        ]
        self.model = build_model(self.events, neighbor_limit=10)

    def test_itemcf_filters_seen_and_uses_learned_neighbor(self) -> None:
        ranked = recommend_itemcf(self.model, user=2, k=2)
        self.assertNotIn(10, ranked)
        self.assertNotIn(30, ranked)
        self.assertEqual(ranked[0], 20)

    def test_random_baseline_is_deterministic_and_filters_seen(self) -> None:
        first = recommend_random(self.model, user=1, k=2, seed=7)
        second = recommend_random(self.model, user=1, k=2, seed=7)
        self.assertEqual(first, second)
        self.assertTrue(set(first).isdisjoint({10, 20}))

    def test_metrics_use_relevant_set_and_rank_discount(self) -> None:
        recall, hit_rate, ndcg = user_metrics([2, 1, 3], {1, 3}, k=3)
        self.assertEqual(recall, 1.0)
        self.assertEqual(hit_rate, 1.0)
        self.assertGreater(ndcg, 0.0)
        self.assertLess(ndcg, 1.0)

    def test_exported_model_can_be_loaded_for_serving(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json.gz"
            export_model(path, self.model, {"model_version": "test-v1"})
            payload = load_model_artifact(path)

        self.assertEqual(payload["metadata"]["model_version"], "test-v1")
        self.assertIn("10", payload["neighbors"])
        self.assertEqual(len(payload["popular_items"]), 4)


if __name__ == "__main__":
    unittest.main()
