"""Regression checks for audit findings that do not need a live Debian host."""
import unittest
from unittest.mock import Mock, patch
from fastapi import HTTPException

import api
from core import background_embeddings as embeddings
from core import desktop_updates
from programmer_agent import api as programmer_api


class AuditEasyFixesTests(unittest.TestCase):
    def test_background_worker_start_is_idempotent(self):
        fake_thread = Mock()
        fake_thread.is_alive.return_value = True
        with patch.object(embeddings, "_worker", None), patch.object(
            embeddings.threading, "Thread", return_value=fake_thread
        ) as thread_factory:
            embeddings.start()
            embeddings.start()
            thread_factory.assert_called_once()
            fake_thread.start.assert_called_once()
        embeddings._stop.set()

    def test_background_worker_reports_error_type_without_sensitive_details(self):
        fake_stop = Mock()
        fake_stop.is_set.side_effect = [False, True]
        with patch.object(embeddings, "_stop", fake_stop), patch.object(
            embeddings, "index_pending_once", side_effect=RuntimeError("private input")
        ), patch("core.logging.log_event") as log:
            embeddings._loop()
            self.assertEqual(log.call_count, 1)
            kwargs = log.call_args.kwargs
            self.assertEqual(kwargs["data"]["error_type"], "RuntimeError")
            self.assertNotIn("private input", str(log.call_args))

    def test_derived_postprocessing_continues_after_failed_summary(self):
        with patch.object(api, "schedule_summary", side_effect=RuntimeError("private")), patch.object(
            api, "refresh_transcript"
        ) as transcript, patch.object(api, "create_episode") as episode, patch(
            "core.logging.log_event"
        ) as log:
            api._postprocess_turn("thread", "question", "answer", "user-id", "assistant-id")
            transcript.assert_called_once_with("thread")
            episode.assert_called_once()
            self.assertEqual(log.call_args.kwargs["data"],
                             {"action": "summary", "error_type": "RuntimeError"})

    def test_create_conversation_does_not_leak_internal_error_as_422(self):
        with patch.object(api, "ensure_conversation",
                          side_effect=RuntimeError("database password is private")):
            with self.assertRaises(HTTPException) as error:
                api.create_conversation(Mock(id="00000000-0000-0000-0000-000000000001", project_id=None))
            self.assertEqual(error.exception.status_code, 500)
            self.assertNotIn("private", error.exception.detail)

    def test_update_service_errors_are_not_client_conflicts(self):
        with patch.object(desktop_updates, "desktop", return_value=False), patch(
            "programmer_agent.releases.status", side_effect=OSError("/private/deploy.env")
        ):
            with self.assertRaises(HTTPException) as error:
                desktop_updates.prepare_server()
            self.assertEqual(error.exception.status_code, 503)
            self.assertNotIn("/private", error.exception.detail)

    def test_programmer_io_error_is_unavailable_not_validation(self):
        with self.assertRaises(HTTPException) as error:
            programmer_api.call(lambda: (_ for _ in ()).throw(OSError("/private/workspace")))
        self.assertEqual(error.exception.status_code, 503)
        self.assertNotIn("/private", error.exception.detail)


if __name__ == "__main__":
    unittest.main()
