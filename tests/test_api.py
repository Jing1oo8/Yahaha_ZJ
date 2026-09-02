from __future__ import annotations

import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path


TEST_DIRECTORY = tempfile.mkdtemp(prefix="yahaha-api-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(TEST_DIRECTORY, 'test.db').as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402
from backend.app.models import utcnow  # noqa: E402
from backend.app.seed import seed  # noqa: E402


class ApiFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        seed(Path("data/processed"), Path("data/artifacts/final_evaluation.json"))

    def setUp(self) -> None:
        self.user = TestClient(app)
        self.admin = TestClient(app)
        user_login = self.user.post(
            "/api/auth/login", json={"username": "alice", "password": "alice123"}
        )
        admin_login = self.admin.post(
            "/api/auth/login", json={"username": "admin", "password": "admin123"}
        )
        self.assertEqual(user_login.status_code, 200)
        self.assertEqual(admin_login.status_code, 200)

    def test_end_to_end_event_dashboard_and_operations(self) -> None:
        feed = self.user.get("/api/feed", params={"type": "personalized", "limit": 5})
        self.assertEqual(feed.status_code, 200)
        body = feed.json()
        self.assertEqual(len(body["items"]), 5)
        self.assertTrue(body["request_id"])
        self.assertTrue(all("source" in item and "score" in item for item in body["items"]))

        first_item = body["items"][0]
        event_types = ["click", "like", "favorite", "not_interested"]
        events = []
        for index, event_type in enumerate(event_types):
            item = body["items"][index]
            event = {
                "event_id": f"test-{event_type}-alice-0001",
                "request_id": body["request_id"],
                "item_id": item["item_id"],
                "event_type": event_type,
                "position": item["position"],
            }
            events.append(event)
            self.assertEqual(self.user.post("/api/events", json=event).status_code, 200)
        duplicate = self.user.post("/api/events", json=events[1])
        self.assertTrue(duplicate.json()["duplicate"])
        profile = self.user.get("/api/profile").json()
        self.assertIn(body["items"][1]["item_id"], profile["positive_items"])
        self.assertIn(body["items"][2]["item_id"], profile["positive_items"])
        self.assertIn(body["items"][3]["item_id"], profile["not_interested_items"])

        for feed_type in ("popular", "explore"):
            first_page = self.user.get(
                "/api/feed", params={"type": feed_type, "limit": 5}
            ).json()
            second_page = self.user.get(
                "/api/feed",
                params={"type": feed_type, "limit": 5, "cursor": first_page["next_cursor"]},
            ).json()
            first_ids = {item["item_id"] for item in first_page["items"]}
            second_ids = {item["item_id"] for item in second_page["items"]}
            self.assertEqual(len(first_ids), 5)
            self.assertTrue(first_ids.isdisjoint(second_ids))

        self.assertEqual(self.user.get("/api/admin/dashboard").status_code, 403)
        dashboard = self.admin.get("/api/admin/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertGreaterEqual(dashboard.json()["exposures"], 5)
        self.assertGreaterEqual(dashboard.json()["likes"], 1)

        boost = self.admin.post(
            "/api/admin/boosts",
            json={
                "item_id": first_item["item_id"],
                "target_user_id": 1,
                "feed_type": "popular",
                "reason": "integration test boost",
                "starts_at": (utcnow() - timedelta(minutes=1)).isoformat(),
                "ends_at": (utcnow() + timedelta(hours=1)).isoformat(),
                "priority": 500,
            },
        )
        self.assertEqual(boost.status_code, 201)
        boosted_feed = self.user.get("/api/feed", params={"type": "popular", "limit": 5})
        self.assertEqual(boosted_feed.json()["items"][0]["item_id"], first_item["item_id"])
        self.assertEqual(boosted_feed.json()["items"][0]["source"], "operator_boost")

        offline = self.admin.patch(
            f"/api/admin/items/{first_item['item_id']}/status",
            json={"status": "offline", "reason": "integration test offline"},
        )
        self.assertEqual(offline.status_code, 200)
        after_offline = self.user.get("/api/feed", params={"type": "popular", "limit": 20})
        returned_ids = {item["item_id"] for item in after_offline.json()["items"]}
        self.assertNotIn(first_item["item_id"], returned_ids)
        self.assertEqual(self.user.get(f"/api/items/{first_item['item_id']}").status_code, 404)

        restored = self.admin.patch(
            f"/api/admin/items/{first_item['item_id']}/status",
            json={"status": "online", "reason": "integration test restore"},
        )
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(self.user.get(f"/api/items/{first_item['item_id']}").status_code, 200)

    def test_users_receive_different_personalized_results(self) -> None:
        bob = TestClient(app)
        self.assertEqual(
            bob.post(
                "/api/auth/login", json={"username": "bob", "password": "bob12345"}
            ).status_code,
            200,
        )
        alice_items = [
            item["item_id"]
            for item in self.user.get(
                "/api/feed", params={"type": "personalized", "limit": 10}
            ).json()["items"]
        ]
        bob_items = [
            item["item_id"]
            for item in bob.get(
                "/api/feed", params={"type": "personalized", "limit": 10}
            ).json()["items"]
        ]
        self.assertNotEqual(alice_items, bob_items)


if __name__ == "__main__":
    unittest.main()
