from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from sqlalchemy import func, select

from .database import Base, SessionLocal, engine
from .models import Item, ModelVersion, User
from .security import hash_password


TEST_USERS = [
    ("alice", "alice123", "user", 1),
    ("bob", "bob12345", "user", 2),
    ("carol", "carol123", "user", 3),
    ("admin", "admin123", "admin", None),
]


def seed(processed_dir: Path, evaluation_path: Path) -> dict[str, int]:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Item)) == 0:
            with (processed_dir / "items.csv").open("r", encoding="utf-8", newline="") as handle:
                db.bulk_insert_mappings(
                    Item,
                    [
                        {
                            "id": int(row["item"]),
                            "title": row["title"],
                            "source_likes": int(row["source_likes"]),
                            "source_views": int(row["source_views"]),
                            "status": "online",
                        }
                        for row in csv.DictReader(handle)
                    ],
                )
        for username, password, role, dataset_user_id in TEST_USERS:
            if not db.scalar(select(User).where(User.username == username)):
                db.add(
                    User(
                        username=username,
                        password_hash=hash_password(password),
                        role=role,
                        dataset_user_id=dataset_user_id,
                    )
                )
        if evaluation_path.is_file():
            report = json.loads(evaluation_path.read_text(encoding="utf-8"))
            version = report["model_version"]
            if not db.get(ModelVersion, version):
                db.add(
                    ModelVersion(
                        version=version,
                        algorithm=report["algorithm"],
                        metrics_json=json.dumps(report["evaluation"]["metrics"]),
                        status="published",
                    )
                )
        db.commit()
        return {
            "items": db.scalar(select(func.count()).select_from(Item)) or 0,
            "users": db.scalar(select(func.count()).select_from(User)) or 0,
            "models": db.scalar(select(func.count()).select_from(ModelVersion)) or 0,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed local application data")
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument(
        "--evaluation", type=Path, default=Path("data/artifacts/final_evaluation.json")
    )
    args = parser.parse_args()
    print(json.dumps(seed(args.processed_dir, args.evaluation), indent=2))


if __name__ == "__main__":
    main()
