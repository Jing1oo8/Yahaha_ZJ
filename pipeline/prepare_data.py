"""Create deterministic, leakage-safe temporal splits for MicroLens-50K."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from inspect_raw import EXPECTED_FILES, inspect


@dataclass(frozen=True, order=True)
class Interaction:
    timestamp: int
    user: int
    item: int


def read_interactions(path: Path) -> tuple[list[Interaction], int]:
    """Read interactions and retain the earliest event per user-item pair."""
    earliest: dict[tuple[int, int], Interaction] = {}
    repeated_pairs = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            event = Interaction(
                timestamp=int(row["timestamp"]),
                user=int(row["user"]),
                item=int(row["item"]),
            )
            key = (event.user, event.item)
            if key in earliest:
                repeated_pairs += 1
                if event < earliest[key]:
                    earliest[key] = event
            else:
                earliest[key] = event
    return sorted(earliest.values()), repeated_pairs


def boundary_timestamp(events: list[Interaction], fraction: float) -> int:
    if not events:
        raise ValueError("Cannot split an empty interaction dataset")
    index = min(int(len(events) * fraction), len(events) - 1)
    return events[index].timestamp


def temporal_split(
    events: list[Interaction],
    train_fraction: float = 0.8,
    validation_fraction: float = 0.1,
) -> tuple[list[Interaction], list[Interaction], list[Interaction], int, int]:
    """Split globally by time, keeping identical timestamps together."""
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1")
    if not 0 < validation_fraction < 1 - train_fraction:
        raise ValueError("validation_fraction must leave a non-empty test fraction")

    ordered = sorted(events)
    validation_start = boundary_timestamp(ordered, train_fraction)
    test_start = boundary_timestamp(ordered, train_fraction + validation_fraction)
    if validation_start >= test_start:
        raise ValueError("Timestamp resolution is too coarse for strict boundaries")

    train = [event for event in ordered if event.timestamp < validation_start]
    validation = [
        event for event in ordered if validation_start <= event.timestamp < test_start
    ]
    test = [event for event in ordered if event.timestamp >= test_start]
    if not train or not validation or not test:
        raise ValueError("Temporal split produced an empty partition")
    return train, validation, test, validation_start, test_start


def known_entity_events(
    events: Iterable[Interaction], history: Iterable[Interaction]
) -> list[Interaction]:
    """Keep events scoreable by a collaborative model fit on history."""
    known_users: set[int] = set()
    known_items: set[int] = set()
    for event in history:
        known_users.add(event.user)
        known_items.add(event.item)
    return [
        event
        for event in events
        if event.user in known_users and event.item in known_items
    ]


def write_interactions(path: Path, events: Iterable[Interaction]) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["user", "item", "timestamp"])
        for event in events:
            writer.writerow([event.user, event.item, event.timestamp])
            count += 1
    return count


def write_item_catalog(raw_dir: Path, output_path: Path) -> int:
    titles: dict[int, str] = {}
    with (raw_dir / EXPECTED_FILES["titles"]).open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        for row in csv.DictReader(handle):
            titles[int(row["item"])] = row["title"]

    display_stats: dict[int, tuple[int, int]] = {}
    with (raw_dir / EXPECTED_FILES["popularity"]).open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        for item, likes, views in csv.reader(handle, delimiter="\t"):
            display_stats[int(item)] = (int(likes), int(views))

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["item", "title", "source_likes", "source_views"])
        for item in sorted(titles):
            likes, views = display_stats[item]
            writer.writerow([item, titles[item], likes, views])
    return len(titles)


def write_user_history(path: Path, events: Iterable[Interaction]) -> int:
    """Write chronological fit-time histories for online seeding and inspection."""
    histories: dict[int, list[Interaction]] = defaultdict(list)
    for event in events:
        histories[event.user].append(event)

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for user in sorted(histories):
            ordered = sorted(histories[user])
            record = {
                "user": user,
                "items": [event.item for event in ordered],
                "timestamps": [event.timestamp for event in ordered],
            }
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
    return len(histories)


def iso_utc(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()


def partition_summary(events: list[Interaction]) -> dict[str, int | str]:
    return {
        "rows": len(events),
        "users": len({event.user for event in events}),
        "items": len({event.item for event in events}),
        "min_timestamp_ms": events[0].timestamp,
        "max_timestamp_ms": events[-1].timestamp,
        "min_utc": iso_utc(events[0].timestamp),
        "max_utc": iso_utc(events[-1].timestamp),
    }


def prepare(raw_dir: Path, output_dir: Path) -> dict[str, object]:
    audit = inspect(raw_dir)
    events, removed_repeated_pairs = read_interactions(
        raw_dir / EXPECTED_FILES["interactions"]
    )
    train, validation, test, validation_start, test_start = temporal_split(events)

    validation_eval = known_entity_events(validation, train)
    train_and_validation = [*train, *validation]
    test_eval = known_entity_events(test, train_and_validation)

    output_dir.mkdir(parents=True, exist_ok=True)
    partitions = {
        "train": train,
        "validation": validation,
        "test": test,
        "validation_eval": validation_eval,
        "test_eval": test_eval,
    }
    for name, partition in partitions.items():
        write_interactions(output_dir / f"{name}.csv", partition)
    catalog_rows = write_item_catalog(raw_dir, output_dir / "items.csv")
    history_users = write_user_history(
        output_dir / "user_history.jsonl", train_and_validation
    )

    assert train[-1].timestamp < validation[0].timestamp
    assert validation[-1].timestamp < test[0].timestamp
    assert len(train) + len(validation) + len(test) == len(events)

    manifest: dict[str, object] = {
        "dataset": "MicroLens-50K",
        "strategy": "global_timestamp_80_10_10",
        "ordering": "timestamp,user,item",
        "deduplication": "keep earliest event per (user,item)",
        "removed_repeated_user_item_rows": removed_repeated_pairs,
        "raw_summary": {
            "interactions": audit["files"]["interactions"]["rows"],
            "users": audit["files"]["interactions"]["unique_users"],
            "items": audit["files"]["interactions"]["unique_items"],
            "min_timestamp_ms": audit["files"]["interactions"]["timestamp_ms"]["min"],
            "min_utc": audit["files"]["interactions"]["timestamp_ms"]["min_utc"],
            "max_timestamp_ms": audit["files"]["interactions"]["timestamp_ms"]["max"],
            "max_utc": audit["files"]["interactions"]["timestamp_ms"]["max_utc"],
        },
        "boundaries": {
            "validation_start_timestamp_ms": validation_start,
            "validation_start_utc": iso_utc(validation_start),
            "test_start_timestamp_ms": test_start,
            "test_start_utc": iso_utc(test_start),
        },
        "partitions": {
            name: partition_summary(partition) for name, partition in partitions.items()
        },
        "evaluation_protocol": {
            "validation": "fit train; evaluate validation_eval",
            "test": "choose configuration on validation, refit train+validation, evaluate test_eval",
            "unknown_entities": "exclude from collaborative metrics and report coverage separately",
        },
        "feature_policy": {
            "titles": "allowed content metadata",
            "source_likes_views_offline": "forbidden in temporal model evaluation because observation times are unknown",
            "source_likes_views_online": "allowed as labeled catalog priors for popular and cold-start feeds",
            "popularity_baseline": "count interactions in the fitting partition only",
        },
        "catalog_rows": catalog_rows,
        "user_history_users": history_users,
        "raw_files": {
            name: {"bytes": details["bytes"], "sha256": details["sha256"]}
            for name, details in audit["files"].items()
        },
    }
    (output_dir / "split_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(prepare(args.raw_dir, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
