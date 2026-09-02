"""Audit the local MicroLens-50K source files without modifying them."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


EXPECTED_FILES = {
    "interactions": "MicroLens-50k_pairs.csv",
    "titles": "MicroLens-50k_titles.csv",
    "popularity": "MicroLens-50k_likes_and_views.txt",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(sorted_values: list[int], fraction: float) -> int | None:
    if not sorted_values:
        return None
    index = math.ceil(fraction * len(sorted_values)) - 1
    return sorted_values[max(0, index)]


def distribution(values: Iterable[int]) -> dict[str, int | float | None]:
    ordered = sorted(values)
    return {
        "min": ordered[0] if ordered else None,
        "p50": percentile(ordered, 0.50),
        "p90": percentile(ordered, 0.90),
        "p95": percentile(ordered, 0.95),
        "max": ordered[-1] if ordered else None,
        "mean": round(sum(ordered) / len(ordered), 4) if ordered else None,
    }


def utc_iso(timestamp_ms: int | None) -> str | None:
    if timestamp_ms is None:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()


def file_info(path: Path) -> dict[str, Any]:
    return {"path": path.as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def inspect_interactions(path: Path) -> tuple[dict[str, Any], set[int]]:
    users: Counter[int] = Counter()
    items: Counter[int] = Counter()
    pairs: Counter[tuple[int, int]] = Counter()
    exact_rows: set[tuple[int, int, int]] = set()
    missing = Counter()
    invalid = Counter()
    row_count = 0
    exact_duplicate_rows = 0
    min_timestamp: int | None = None
    max_timestamp: int | None = None

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        if columns != ["user", "item", "timestamp"]:
            raise ValueError(f"Unexpected interaction columns: {columns}")
        for row in reader:
            row_count += 1
            for column in columns:
                if row[column] is None or not row[column].strip():
                    missing[column] += 1
            try:
                user = int(row["user"])
            except (TypeError, ValueError):
                invalid["user"] += 1
                continue
            try:
                item = int(row["item"])
            except (TypeError, ValueError):
                invalid["item"] += 1
                continue
            try:
                timestamp = int(row["timestamp"])
            except (TypeError, ValueError):
                invalid["timestamp"] += 1
                continue
            users[user] += 1
            items[item] += 1
            pairs[(user, item)] += 1
            exact_row = (user, item, timestamp)
            if exact_row in exact_rows:
                exact_duplicate_rows += 1
            exact_rows.add(exact_row)
            min_timestamp = timestamp if min_timestamp is None else min(min_timestamp, timestamp)
            max_timestamp = timestamp if max_timestamp is None else max(max_timestamp, timestamp)

    duplicate_pairs = sum(count - 1 for count in pairs.values() if count > 1)
    report = {
        **file_info(path),
        "columns": ["user", "item", "timestamp"],
        "rows": row_count,
        "valid_rows": sum(users.values()),
        "missing_values": dict(missing),
        "invalid_values": dict(invalid),
        "unique_users": len(users),
        "unique_items": len(items),
        "exact_duplicate_rows": exact_duplicate_rows,
        "repeated_user_item_rows": duplicate_pairs,
        "timestamp_ms": {
            "min": min_timestamp,
            "max": max_timestamp,
            "min_utc": utc_iso(min_timestamp),
            "max_utc": utc_iso(max_timestamp),
        },
        "interactions_per_user": distribution(users.values()),
        "interactions_per_item": distribution(items.values()),
    }
    return report, set(items)


def inspect_titles(path: Path) -> tuple[dict[str, Any], set[int]]:
    item_counts: Counter[int] = Counter()
    title_lengths: list[int] = []
    missing = Counter()
    invalid_item_ids = 0
    row_count = 0

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        if columns != ["item", "title"]:
            raise ValueError(f"Unexpected title columns: {columns}")
        for row in reader:
            row_count += 1
            for column in columns:
                if row[column] is None or not row[column].strip():
                    missing[column] += 1
            try:
                item = int(row["item"])
            except (TypeError, ValueError):
                invalid_item_ids += 1
                continue
            item_counts[item] += 1
            title_lengths.append(len(row["title"] or ""))

    report = {
        **file_info(path),
        "columns": ["item", "title"],
        "rows": row_count,
        "unique_items": len(item_counts),
        "missing_values": dict(missing),
        "invalid_item_ids": invalid_item_ids,
        "duplicate_item_rows": sum(count - 1 for count in item_counts.values() if count > 1),
        "title_length_characters": distribution(title_lengths),
    }
    return report, set(item_counts)


def inspect_popularity(path: Path) -> tuple[dict[str, Any], set[int]]:
    item_counts: Counter[int] = Counter()
    likes: list[int] = []
    views: list[int] = []
    malformed_rows = 0
    invalid_values = Counter()
    row_count = 0

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            row_count += 1
            if len(row) != 3:
                malformed_rows += 1
                continue
            parsed: list[int] = []
            for column, value in zip(("item", "likes", "views"), row):
                try:
                    parsed.append(int(value))
                except ValueError:
                    invalid_values[column] += 1
                    break
            if len(parsed) != 3:
                continue
            item, like_count, view_count = parsed
            item_counts[item] += 1
            likes.append(like_count)
            views.append(view_count)

    report = {
        **file_info(path),
        "columns": ["item", "likes", "views"],
        "delimiter": "tab",
        "header": False,
        "rows": row_count,
        "unique_items": len(item_counts),
        "malformed_rows": malformed_rows,
        "invalid_values": dict(invalid_values),
        "duplicate_item_rows": sum(count - 1 for count in item_counts.values() if count > 1),
        "likes": distribution(likes),
        "views": distribution(views),
        "rows_with_likes_over_views": sum(like > view for like, view in zip(likes, views)),
    }
    return report, set(item_counts)


def inspect(raw_dir: Path) -> dict[str, Any]:
    paths = {name: raw_dir / filename for name, filename in EXPECTED_FILES.items()}
    missing_files = [str(path) for path in paths.values() if not path.is_file()]
    if missing_files:
        raise FileNotFoundError(f"Missing required raw files: {missing_files}")

    interactions, interaction_items = inspect_interactions(paths["interactions"])
    titles, title_items = inspect_titles(paths["titles"])
    popularity, popularity_items = inspect_popularity(paths["popularity"])
    return {
        "dataset": "MicroLens-50K",
        "raw_directory": raw_dir.as_posix(),
        "files": {
            "interactions": interactions,
            "titles": titles,
            "popularity": popularity,
        },
        "item_coverage": {
            "interaction_items_without_title": len(interaction_items - title_items),
            "interaction_items_without_popularity": len(interaction_items - popularity_items),
            "title_items_without_interaction": len(title_items - interaction_items),
            "popularity_items_without_interaction": len(popularity_items - interaction_items),
            "title_items_without_popularity": len(title_items - popularity_items),
            "popularity_items_without_title": len(popularity_items - title_items),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = inspect(args.raw_dir)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
