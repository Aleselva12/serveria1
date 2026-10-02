import os
import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from core.access import owner_dependency
from core.component_bus import ComponentBus
from core.protocol import ComponentResult, TaskEnvelope
from core.run_lifecycle import TRANSITIONS


class ProtocolBusTests(unittest.TestCase):
    def envelope(self):
        return TaskEnvelope(
            run_id="00000000-0000-0000-0000-000000000001",
            thread_id="thread",
            source="supervisor",
            target="worker",
            capability="test",
            payload={"value": 7},
        )

    def test_protocol_is_strict_and_bus_is_direct(self):
        envelope = self.envelope()
        bus = ComponentBus()
        seen = []

        def handler(task):
            seen.append(task)
            return "ok"

        result = bus.dispatch(envelope, handler)
        self.assertEqual(seen[0], envelope)
        self.assertIsInstance(result, ComponentResult)
        self.assertEqual(result.content, "ok")
        self.assertEqual(result.status, "completed")
        self.assertEqual(bus.snapshot()["worker"]["status"], "ready")
        self.assertIsNotNone(result.duration_ms)

        with self.assertRaises(ValidationError):
            TaskEnvelope(
                run_id="x", thread_id="t", source="a", target="b",
                capability="c", unknown=True,
            )

    def test_lifecycle_transition_map_has_no_terminal_escape(self):
        for status in ("completed", "failed", "cancelled", "timed_out"):
            self.assertEqual(TRANSITIONS[status], set())
        self.assertIn("waiting_approval", TRANSITIONS["running"])
        self.assertIn("completed", TRANSITIONS["running"])


class OwnerAccessTests(unittest.TestCase):
    def app(self):
        app = FastAPI()

        @app.get("/protected", dependencies=[Depends(owner_dependency("files"))])
        def protected():
            return {"ok": True}

        return app

    def test_shared_owner_token_wins_over_legacy_token(self):
        with patch.dict(
            os.environ,
            {"CORA_OWNER_TOKEN": "shared", "CORA_FILES_TOKEN": "legacy"},
            clear=False,
        ), TestClient(self.app()) as client:
            self.assertEqual(
                client.get("/protected", headers={"Authorization": "Bearer legacy"}).status_code,
                401,
            )
            self.assertEqual(
                client.get("/protected", headers={"Authorization": "Bearer shared"}).status_code,
                200,
            )

    def test_legacy_token_still_works_during_migration(self):
        with patch.dict(
            os.environ,
            {"CORA_OWNER_TOKEN": "", "CORA_FILES_TOKEN": "legacy"},
            clear=False,
        ), TestClient(self.app()) as client:
            self.assertEqual(
                client.get("/protected", headers={"Authorization": "Bearer legacy"}).status_code,
                200,
            )


if __name__ == "__main__":
    unittest.main()
