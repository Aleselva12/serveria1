"""Project check tests: never need running services or real data."""
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core import project_checks as pc


class ProjectChecksTests(unittest.TestCase):
    def setUp(self):
        self.before = pc._LAST
        pc._LAST = None
        self.addCleanup(setattr, pc, "_LAST", self.before)

    def test_not_checked_is_never_healthy(self):
        snapshot = pc.snapshot()
        self.assertIsNone(snapshot["checkedAt"])
        self.assertEqual(snapshot["checks"], [])
        self.assertEqual(snapshot["scope"], "preflight_only")

    def test_read_only_checks_isolate_failures_and_never_claim_end_to_end(self):
        with patch.dict(pc._PROBES, {
            "database": lambda: ("pass", "SELECT 1"),
            "library": lambda: ("pass", "Folder readable"),
            "audio": lambda: (_ for _ in ()).throw(OSError("private detail")),
            "ollama": lambda: ("unknown", "Not configured"),
        }, clear=True):
            snapshot = pc.run_once()
        states = {item["id"]: item["status"] for item in snapshot["checks"]}
        self.assertEqual(states, {
            "database": "pass", "library": "pass",
            "audio": "fail", "ollama": "unknown",
        })
        self.assertEqual(snapshot["scope"], "preflight_only")
        self.assertNotIn("private detail", str(snapshot))
        self.assertIsNotNone(pc.snapshot()["checkedAt"])

    def test_copy_of_snapshot_cannot_mutate_cached_result(self):
        with patch.dict(pc._PROBES, {key: (lambda: ("pass", "Only prerequisites")) for key in pc.CHECKS}):
            pc.run_once()
        first = pc.snapshot()
        first["checks"][0]["status"] = "fail"
        self.assertEqual(pc.snapshot()["checks"][0]["status"], "pass")

    def test_endpoint_reports_scope_and_does_not_trigger_checks_on_get(self):
        with patch.object(pc, "run_once", side_effect=AssertionError("must not run on GET")):
            app = FastAPI()
            app.include_router(pc.router)
            response = TestClient(app).get("/api/v1/project/checks")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["scope"], "preflight_only")


if __name__ == "__main__":
    unittest.main()
