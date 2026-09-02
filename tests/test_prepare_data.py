from __future__ import annotations

import sys
import tempfile
import unittest
import json
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from prepare_data import (  # noqa: E402
    Interaction,
    known_entity_events,
    temporal_split,
    write_user_history,
)


class TemporalSplitTest(unittest.TestCase):
    def test_equal_timestamps_never_cross_partitions(self) -> None:
        events = [
            Interaction(timestamp=timestamp, user=index, item=index)
            for index, timestamp in enumerate([1, 2, 3, 4, 5, 6, 7, 8, 8, 9, 10])
        ]

        train, validation, test, validation_start, test_start = temporal_split(
            events, train_fraction=0.6, validation_fraction=0.2
        )

        self.assertLess(max(event.timestamp for event in train), validation_start)
        self.assertTrue(all(event.timestamp >= validation_start for event in validation))
        self.assertLess(max(event.timestamp for event in validation), test_start)
        self.assertTrue(all(event.timestamp >= test_start for event in test))
        self.assertEqual(len(events), len(train) + len(validation) + len(test))

    def test_evaluation_keeps_only_entities_known_at_fit_time(self) -> None:
        history = [
            Interaction(timestamp=1, user=1, item=10),
            Interaction(timestamp=2, user=2, item=20),
        ]
        future = [
            Interaction(timestamp=3, user=1, item=20),
            Interaction(timestamp=4, user=3, item=20),
            Interaction(timestamp=5, user=1, item=30),
        ]

        self.assertEqual(known_entity_events(future, history), [future[0]])

    def test_user_history_is_chronological_and_deterministic(self) -> None:
        events = [
            Interaction(timestamp=3, user=2, item=30),
            Interaction(timestamp=2, user=1, item=20),
            Interaction(timestamp=1, user=1, item=10),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.jsonl"
            self.assertEqual(write_user_history(path, events), 2)
            records = [json.loads(line) for line in path.read_text().splitlines()]

        self.assertEqual(records[0], {"user": 1, "items": [10, 20], "timestamps": [1, 2]})
        self.assertEqual(records[1]["user"], 2)


if __name__ == "__main__":
    unittest.main()
