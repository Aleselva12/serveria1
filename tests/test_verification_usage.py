from datetime import datetime, timedelta, timezone
import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from core import verification_usage as usage
from core import project_checks


class UsageEvidenceTests(unittest.TestCase):
    def test_all_thirty_checks_have_runners_and_explicit_scope(self):
        from core.health_catalog import CATALOG
        from deploy.verify_nodes import available_checks
        self.assertEqual(len(CATALOG), 30)
        self.assertEqual(set(available_checks()), set(CATALOG))
        self.assertEqual(CATALOG["gmail_e2e"]["kind"], "synthetic")
        self.assertEqual(CATALOG["immich_e2e"]["kind"], "preflight")
        self.assertEqual(CATALOG["backup_restore"]["kind"], "synthetic")

    def test_confirmed_worker_reply_updates_only_explicit_targets_and_chat_route(self):
        reply = {"model": "selected:8b", "done": True, "message": {"role":"assistant", "content":"OK"}}
        with patch.object(usage, "worker_ids", return_value=["desktop_e2e"]), patch.object(usage, "record") as record:
            self.assertEqual(usage.worker_reply("pc", "selected:8b", reply, chat=True), "pass")
            self.assertEqual([c.args[0] for c in record.call_args_list], ["desktop_e2e", "worker_e2e"])
            self.assertTrue(all(c.args[1] == "pass" for c in record.call_args_list))
            record.reset_mock()
            self.assertEqual(usage.worker_reply("pc", "selected:8b", {"actual_model":"other:8b", "done":True, "response":"OK"}, chat=False), "fail")
            record.assert_called_once()
            self.assertEqual(record.call_args.args[:2], ("desktop_e2e", "fail"))

    def test_wrong_worker_model_never_returns_a_reply_or_calls_local_ollama(self):
        from core import agent_models
        with patch.object(agent_models, "remote_machine", return_value={}), patch.object(agent_models, "require_agent_chat"), patch("core.machines_api._worker_call", return_value={"model":"wrong", "done":True, "message":{"role":"assistant", "content":"OK"}}), patch.object(usage, "worker_ids", return_value=[]), patch.object(usage, "record"), patch("langchain_ollama.ChatOllama._create_chat_stream") as local:
            with self.assertRaises(HTTPException) as error:
                agent_models.chat_on_worker("pc", "selected", {})
            self.assertEqual(error.exception.status_code, 502)
            local.assert_not_called()

    def test_calendar_readback_is_required_before_green_and_never_repeats_write(self):
        from core import google_calendar
        event = dict(id="private-id",version=1,title="private-title",start="start",end="end")
        with patch.object(usage, "enabled", return_value=True), patch.object(google_calendar, "get_event", return_value=event), patch.object(google_calendar, "create_event") as create, patch.object(usage, "record") as record:
            usage.calendar_write("create", event)
            self.assertEqual(record.call_args.args[:2], ("calendar_e2e", "pass"))
            self.assertNotIn("private", record.call_args.args[2])
            create.assert_not_called()
        with patch.object(usage, "enabled", return_value=True), patch.object(google_calendar, "get_event", side_effect=OSError("private-error")), patch.object(usage, "record") as record:
            usage.calendar_write("create", event)
            self.assertEqual(record.call_args.args[1], "unknown")
            self.assertNotIn("private-error", record.call_args.args[2])

    def test_synthetic_runs_cannot_publish_live_evidence_or_read_google(self):
        from core import google_calendar
        with patch.dict(os.environ, {"CORA_VERIFICATION_SYNTHETIC":"1"}), patch("core.database.DATABASE_URL", "configured"), patch("core.project_checks._release", return_value="a"*40), patch("core.database.db_connection") as db, patch.object(google_calendar, "get_event") as read:
            self.assertFalse(usage.record("worker_e2e", "pass", "fake"))
            usage.calendar_write("create", {"id":"fake"})
            read.assert_not_called()
            db.assert_not_called()

    def test_recovery_is_recorded_immediately_even_inside_throttle_window(self):
        usage._last.clear()
        self.addCleanup(usage._last.clear)
        with patch.object(usage, "enabled", return_value=True), patch("core.database.db_connection") as db, patch("core.project_checks._release", return_value="a"*40):
            for status in ("pass", "fail", "pass", "pass"):
                usage.record("worker_e2e", status, "same operation")
            self.assertEqual(db.return_value.__enter__.return_value.execute.call_count, 3)

    def test_runtime_evidence_survives_missing_fixture_without_forging_freshness(self):
        now = datetime.now(timezone.utc)
        def row(status, detail, at):
            return dict(check_id="calendar_e2e", status=status,detail=detail,source="manual",environment="debian-api",commit_sha="a"*40,duration_ms=1,observed_at=at)
        for age, expected, proof_status in ((60,"pass","pass"),(2*86400,"unknown","pass"),(60,"unknown","unknown")):
            conn = MagicMock()
            current = row("unknown", "Account test non configurato", now)
            proof = row(proof_status, "Uso reale: scrittura riletta", now-timedelta(seconds=age))
            conn.execute.side_effect = [MagicMock(fetchall=lambda:[current]), MagicMock(fetchall=lambda:[]), MagicMock(fetchall=lambda:[proof])]
            with patch("core.database.db_connection") as db, patch.object(project_checks,"_release",return_value="a"*40), patch.object(project_checks,"_environment",return_value="debian-api"):
                db.return_value.__enter__.return_value = conn
                result = project_checks.health_dashboard()["latest"]["calendar_e2e"]
            self.assertEqual(result["status"], expected)
            if expected == "pass": self.assertEqual(result["at"], proof["observed_at"].isoformat())


if __name__ == "__main__":
    unittest.main()
