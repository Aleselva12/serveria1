"""Regression checks for audit findings that do not need a live Debian host."""
import unittest
from unittest.mock import Mock, patch
from fastapi import HTTPException

import api
from core import background_embeddings as embeddings
from core import desktop_updates
from programmer_agent import api as programmer_api


class AuditEasyFixesTests(unittest.TestCase):
    def test_lifespan_cleans_up_after_worker_start_failure(self):
        import asyncio
        from unittest.mock import call

        order = []
        def mark(name, fails=False):
            def execute():
                order.append(name)
                if fails:
                    raise RuntimeError("synthetic worker start failure")
            return execute
        with patch.object(api, "validate_runtime_profile"), patch(
            "core.runtime.recover_interrupted"
        ), patch("core.observability.archive.start", mark("archive.start")), patch(
            "core.observability.archive.stop", mark("archive.stop")
        ), patch("core.background_embeddings.start", mark("embeddings.start")), patch(
            "core.background_embeddings.stop", mark("embeddings.stop")
        ), patch("core.library_monitor.start", mark("library.start", fails=True)), patch(
            "core.library_monitor.stop", mark("library.stop")
        ), patch("core.project_checks.stop", mark("checks.stop")), patch(
            "core.project_checks.start", mark("checks.start")
        ), patch.object(api, "close_pool", mark("pool.close")):
            async def check():
                async with api.lifespan(None):
                    self.fail("Cannot reach application startup")
            with self.assertRaisesRegex(RuntimeError, "synthetic worker"):
                asyncio.run(check())
        self.assertEqual(order, ["archive.start", "embeddings.start", "library.start",
                                 "library.stop", "checks.stop", "embeddings.stop",
                                 "archive.stop", "pool.close"])

    def test_lifespan_continues_cleanup_after_failed_stop(self):
        import asyncio
        order = []
        def mark(name, fails=False):
            def execute():
                order.append(name)
                if fails:
                    raise RuntimeError("synthetic stop failure")
            return execute
        with patch.object(api, "validate_runtime_profile"), patch(
            "core.runtime.recover_interrupted"
        ), patch("core.observability.archive.start", mark("archive.start")), patch(
            "core.observability.archive.stop", mark("archive.stop")
        ), patch("core.background_embeddings.start", mark("embeddings.start")), patch(
            "core.background_embeddings.stop", mark("embeddings.stop")
        ), patch("core.library_monitor.start", mark("library.start")), patch(
            "core.library_monitor.stop", mark("library.stop", fails=True)
        ), patch("core.project_checks.start", mark("checks.start")), patch(
            "core.project_checks.stop", mark("checks.stop")
        ), patch.object(api, "notification_worker") as notify, patch.object(
            api.runtime, "shutdown", mark("runtime.shutdown")
        ), patch.object(api, "close_pool", mark("pool.close")):
            notify.start.side_effect = mark("notify.start")
            notify.stop.side_effect = mark("notify.stop")
            async def check():
                async with api.lifespan(None):
                    pass
            with self.assertRaisesRegex(RuntimeError, "synthetic stop"):
                asyncio.run(check())
        self.assertEqual(order[-7:], ["notify.stop", "runtime.shutdown", "library.stop",
                                      "checks.stop", "embeddings.stop", "archive.stop",
                                      "pool.close"])

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
        embeddings._stop.clear()  # Leave the shared module in its original idle state.

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

    def test_notification_worker_reports_cycle_failure_without_private_data(self):
        from core.notifications import NotificationWorker
        notification = NotificationWorker()
        notification._stop.wait = Mock(side_effect=[False, True])
        with patch("core.notifications.deliver_calendar_reminders",
                   side_effect=OSError("/private/calendar/data")):
            notification._run()
        health = notification.health()
        self.assertEqual(health["last_error_type"], "OSError")
        self.assertIsNotNone(health["last_attempt"])
        self.assertNotIn("/private", str(health))
        notification._stop.wait.side_effect = [False, True]
        with patch("core.notifications.deliver_calendar_reminders"):
            notification._run()
        self.assertIsNone(notification.health()["last_error_type"])
        self.assertIsNotNone(notification.health()["last_success"])

    def test_runtime_routes_have_no_duplicate_http_method_path_pairs(self):
        from fastapi.routing import APIRoute
        pairs = [(method, route.path) for route in api.app.routes
                 if isinstance(route, APIRoute)
                 for method in route.methods]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_programmer_io_error_is_unavailable_not_validation(self):
        with self.assertRaises(HTTPException) as error:
            programmer_api.call(lambda: (_ for _ in ()).throw(OSError("/private/workspace")))
        self.assertEqual(error.exception.status_code, 503)
        self.assertNotIn("/private", error.exception.detail)


if __name__ == "__main__":
    unittest.main()
