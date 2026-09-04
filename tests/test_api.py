from __future__ import annotations

import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path


TEST_DIRECTORY = tempfile.mkdtemp(prefix="yahaha-api-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(TEST_DIRECTORY, 'test.db').as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.database import SessionLocal  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.models import Exposure, utcnow  # noqa: E402
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
        self.assertTrue(
            all("source" in item and "score" in item and "cover_url" in item for item in body["items"])
        )

        first_item = body["items"][0]
        boost_item = body["items"][4]
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
        self.assertIn(body["items"][0]["item_id"], profile["clicked_items"])
        self.assertIn(body["items"][1]["item_id"], profile["positive_items"])
        self.assertIn(body["items"][2]["item_id"], profile["positive_items"])
        self.assertIn(body["items"][1]["item_id"], profile["liked_items"])
        self.assertIn(body["items"][2]["item_id"], profile["favorite_items"])
        self.assertEqual(profile["clicked_details"][0]["title"], body["items"][0]["title"])
        self.assertIn("source_views", profile["favorite_details"][0])
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
        self.assertGreaterEqual(dashboard.json()["active_users"], 1)
        self.assertEqual(len(dashboard.json()["feed_shares"]), 3)
        self.assertTrue(dashboard.json()["popular_items"])
        self.assertTrue(dashboard.json()["trend"])
        self.assertTrue(dashboard.json()["recent_requests"])

        trace = self.admin.get(f"/api/admin/requests/{body['request_id']}")
        self.assertEqual(trace.status_code, 200)
        self.assertEqual(trace.json()["request_id"], body["request_id"])
        self.assertEqual(len(trace.json()["exposures"]), 5)
        self.assertGreaterEqual(len(trace.json()["events"]), 5)

        users = self.admin.get("/api/admin/users")
        self.assertEqual(users.status_code, 200)
        alice = next(user for user in users.json() if user["username"] == "alice")
        debug_profile = self.admin.get(f"/api/admin/users/{alice['user_id']}/profile")
        self.assertEqual(debug_profile.status_code, 200)
        self.assertEqual(debug_profile.json()["username"], "alice")
        self.assertTrue(debug_profile.json()["history_details"])
        self.assertTrue(debug_profile.json()["positive_details"])
        self.assertTrue(debug_profile.json()["recommendation_preview"])
        self.assertEqual(self.user.get("/api/admin/users").status_code, 403)

        exported = self.admin.get("/api/admin/dashboard/export", params={"range": "24h"})
        self.assertEqual(exported.status_code, 200)
        self.assertIn("text/csv", exported.headers["content-type"])
        self.assertIn("attachment", exported.headers["content-disposition"])
        self.assertIn(body["request_id"], exported.text)
        self.assertEqual(self.user.get("/api/admin/dashboard/export").status_code, 403)
        self.assertEqual(
            self.user.get(f"/api/admin/requests/{body['request_id']}").status_code,
            403,
        )
        self.assertEqual(
            self.admin.get("/api/admin/dashboard", params={"range": "invalid"}).status_code,
            422,
        )

        boost = self.admin.post(
            "/api/admin/boosts",
            json={
                "item_id": boost_item["item_id"],
                "target_user_id": 1,
                "feed_type": "popular",
                "reason": "integration test boost",
                "starts_at": (utcnow() - timedelta(minutes=1)).isoformat(),
                "ends_at": (utcnow() + timedelta(hours=1)).isoformat(),
                "priority": 500,
            },
        )
        self.assertEqual(boost.status_code, 201)
        overlapping_boost = self.admin.post(
            "/api/admin/boosts",
            json={
                "item_id": boost_item["item_id"],
                "target_user_id": 1,
                "feed_type": "popular",
                "reason": "lower priority overlapping boost",
                "starts_at": (utcnow() - timedelta(minutes=1)).isoformat(),
                "ends_at": (utcnow() + timedelta(hours=1)).isoformat(),
                "priority": 300,
            },
        )
        self.assertEqual(overlapping_boost.status_code, 201)
        boost_rules = self.admin.get("/api/admin/boosts")
        self.assertEqual(boost_rules.status_code, 200)
        matching_rules = [
            rule for rule in boost_rules.json() if rule["item_id"] == boost_item["item_id"]
        ]
        self.assertEqual(len(matching_rules), 2)
        self.assertEqual({rule["priority"] for rule in matching_rules}, {300, 500})
        self.assertTrue(all(rule["duration_seconds"] > 0 for rule in matching_rules))
        self.assertEqual(self.user.get("/api/admin/boosts").status_code, 403)
        boosted_feed = self.user.get("/api/feed", params={"type": "popular", "limit": 5})
        self.assertEqual(boosted_feed.status_code, 200)
        boosted_items = boosted_feed.json()["items"]
        self.assertEqual(boosted_items[0]["item_id"], boost_item["item_id"])
        self.assertEqual(boosted_items[0]["source"], "operator_boost")
        self.assertEqual(boosted_items[0]["score"], 500.0)
        self.assertEqual(
            sum(item["item_id"] == boost_item["item_id"] for item in boosted_items),
            1,
        )
        boosted_click = {
            "event_id": "test-click-boosted-alice-0001",
            "request_id": boosted_feed.json()["request_id"],
            "item_id": boosted_items[0]["item_id"],
            "event_type": "click",
            "position": boosted_items[0]["position"],
        }
        self.assertEqual(self.user.post("/api/events", json=boosted_click).status_code, 200)
        after_click = self.user.get("/api/feed", params={"type": "popular", "limit": 20})
        self.assertNotIn(
            boost_item["item_id"],
            {item["item_id"] for item in after_click.json()["items"]},
        )

        offline = self.admin.patch(
            f"/api/admin/items/{boost_item['item_id']}/status",
            json={"status": "offline", "reason": "integration test offline"},
        )
        self.assertEqual(offline.status_code, 200)
        offline_items = self.admin.get("/api/admin/items", params={"status": "offline"})
        self.assertEqual(offline_items.status_code, 200)
        self.assertIn(boost_item["item_id"], {item["item_id"] for item in offline_items.json()})
        self.assertTrue(all(item["status"] == "offline" for item in offline_items.json()))
        after_offline = self.user.get("/api/feed", params={"type": "popular", "limit": 20})
        returned_ids = {item["item_id"] for item in after_offline.json()["items"]}
        self.assertNotIn(boost_item["item_id"], returned_ids)
        self.assertEqual(self.user.get(f"/api/items/{boost_item['item_id']}").status_code, 404)

        restored = self.admin.patch(
            f"/api/admin/items/{boost_item['item_id']}/status",
            json={"status": "online", "reason": "integration test restore"},
        )
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(self.user.get(f"/api/items/{boost_item['item_id']}").status_code, 200)

    def test_exposure_cooldown_allows_old_items_to_return(self) -> None:
        viewer = TestClient(app)
        registered = viewer.post(
            "/api/auth/register",
            json={"username": "cooldown_user", "password": "strongpass123"},
        )
        self.assertEqual(registered.status_code, 201)
        user_id = registered.json()["id"]

        first_feed = viewer.get("/api/feed", params={"type": "popular", "limit": 1}).json()
        first_item_id = first_feed["items"][0]["item_id"]
        recent_feed = viewer.get("/api/feed", params={"type": "popular", "limit": 50}).json()
        self.assertNotIn(first_item_id, {item["item_id"] for item in recent_feed["items"]})

        with SessionLocal() as db:
            db.query(Exposure).filter(
                Exposure.user_id == user_id,
                Exposure.item_id == first_item_id,
            ).update({Exposure.created_at: utcnow() - timedelta(hours=25)})
            db.commit()

        cooled_feed = viewer.get("/api/feed", params={"type": "popular", "limit": 50}).json()
        self.assertIn(first_item_id, {item["item_id"] for item in cooled_feed["items"]})

    def test_registration_creates_isolated_cold_start_user(self) -> None:
        newcomer = TestClient(app)
        registered = newcomer.post(
            "/api/auth/register",
            json={"username": "New_User", "password": "strongpass123"},
        )
        self.assertEqual(registered.status_code, 201)
        self.assertEqual(registered.json()["username"], "new_user")
        self.assertEqual(registered.json()["role"], "user")
        self.assertIsNone(newcomer.get("/api/profile").json()["dataset_user_id"])
        feed = newcomer.get("/api/feed", params={"type": "personalized", "limit": 3})
        self.assertEqual(feed.status_code, 200)
        self.assertEqual(len(feed.json()["items"]), 3)
        duplicate = TestClient(app).post(
            "/api/auth/register",
            json={"username": "new_user", "password": "anotherpass123"},
        )
        self.assertEqual(duplicate.status_code, 409)
        short_password = TestClient(app).post(
            "/api/auth/register",
            json={"username": "short_password", "password": "short"},
        )
        self.assertEqual(short_password.status_code, 422)

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
