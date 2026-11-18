"""Word notes waiting for the owner, listed in Notifiche › Da decidere."""
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.domain import commercial_notes


class PendingOverviewTests(unittest.TestCase):
    def test_only_live_pending_proposals_outside_collaudi_are_listed(self):
        conn = MagicMock()
        at = datetime(2026, 11, 18, 9, tzinfo=UTC)
        conn.execute.return_value.fetchall.return_value = [
            {"id": uuid4(), "audio_id": uuid4(), "title": None, "created_at": at, "expires_at": at}]

        @contextmanager
        def connect():
            yield conn
        with patch.object(commercial_notes, "db_connection", connect):
            items = commercial_notes.pending_overview()
        sql = conn.execute.call_args.args[0]
        for clause in ("status='pending'", "expires_at > NOW()", "IS DISTINCT FROM 'collaudo'"):
            self.assertIn(clause, sql)
        self.assertEqual(items[0]["title"], "Registrazione")
        self.assertEqual(set(items[0]), {"id", "audioId", "title", "createdAt", "expiresAt"})

    def test_endpoint_is_not_shadowed_by_the_recording_routes(self):
        from core.api import audio_api
        app = FastAPI()
        app.include_router(audio_api.router)
        for dependency in audio_api.router.dependencies:
            app.dependency_overrides[dependency.dependency] = lambda: None
        with patch.object(commercial_notes, "pending_overview", return_value=[{"id": "x"}]):
            response = TestClient(app).get("/api/v1/audio/commercial/pending")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": [{"id": "x"}]})


if __name__ == "__main__":
    unittest.main()
