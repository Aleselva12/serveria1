import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import release_identity
from deploy import verify_nodes as verifier


class VerificationTests(unittest.TestCase):
    def test_missing_prerequisites_do_not_run_or_pass(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(verifier, "_child") as child:
            for check in ("memory_e2e", "calendar_e2e"):
                self.assertEqual(verifier.run(check)["status"], "unknown")
            child.assert_not_called()

    def test_production_calendar_token_is_rejected_even_when_enabled(self):
        with tempfile.NamedTemporaryFile() as token, patch.dict(os.environ, {
            "CORA_VERIFY_CALENDAR_TEST_ACCOUNT": "yes",
            "CORA_VERIFY_CALENDAR_TOKEN_PATH": token.name,
            "CORA_GOOGLE_CALENDAR_TOKEN_PATH": token.name,
        }):
            self.assertFalse(verifier._calendar_ready())

    def test_memory_runs_in_distinct_processes_and_always_cleans_up(self):
        with patch.dict(os.environ, {"CORA_DATABASE_URL": "configured"}), patch.object(
            verifier, "_child", side_effect=[{"status": "pass"}, {"status": "pass"}, {"status": "pass"}]
        ) as child:
            self.assertEqual(verifier.run("memory_e2e")["status"], "pass")
        self.assertEqual([c.args[0] for c in child.call_args_list], ["memory_write", "memory_read", "memory_cleanup"])
        self.assertEqual(len({c.args[1] for c in child.call_args_list}), 1)

    def test_cleanup_failure_overrides_success_and_initial_failure(self):
        for first in ("pass", "fail"):
            responses = [{"status": first}]
            if first == "pass": responses.append({"status": "pass"})
            responses.append({"status": "fail"})
            with patch.dict(os.environ, {"CORA_DATABASE_URL": "configured"}), patch.object(
                verifier, "_child", side_effect=responses
            ):
                result = verifier.run("memory_e2e")
                self.assertEqual(result["status"], "fail")
                self.assertIn("Pulizia", result["detail"])

    def test_timeout_still_attempts_fixture_cleanup(self):
        with patch.dict(os.environ, {"CORA_DATABASE_URL": "configured"}), patch.object(
            verifier, "_child", side_effect=[subprocess.TimeoutExpired("test", 90), {"status": "pass"}]
        ) as child:
            self.assertEqual(verifier.run("memory_e2e")["status"], "fail")
            self.assertEqual(child.call_args_list[-1].args[0], "memory_cleanup")

    def test_worker_disabled_is_skipped_without_inference(self):
        with patch.dict(os.environ, {"CORA_VERIFY_DESKTOP_ID": "desktop"}), patch(
            "core.machines_api._find", return_value={"enabled": False}
        ), patch("core.machines_api.test_worker_inference") as infer:
            self.assertEqual(verifier._action("desktop_e2e", "a"*32)["status"], "skipped")
            infer.assert_not_called()

    def test_worker_old_protocol_and_wrong_actual_model_cannot_pass(self):
        with patch.dict(os.environ, {"CORA_VERIFY_DESKTOP_ID": "desktop"}), patch(
            "core.machines_api._find", return_value={"enabled": True, "selected_model": "chosen:8b"}
        ), patch("core.machines_api.test_worker_inference", return_value={"response": "CORA_WORKER_OK"}) as infer:
            self.assertEqual(verifier._action("desktop_e2e", "a"*32)["status"], "unknown")
            infer.return_value = {"actual_model": "different:8b", "done": True, "response": "CORA_WORKER_OK"}
            with self.assertRaises(ValueError): verifier._action("desktop_e2e", "a"*32)

    def test_worker_challenge_rejects_false_positive_responses(self):
        run_id = "a" * 32
        valid = {"model":"chosen:8b", "done":True, "message":{"role":"assistant", "content":"CORA_" + run_id}}
        from copy import deepcopy
        with patch("core.agent_models.binding", return_value={"machine_id":"remote", "model":"chosen:8b"}), patch("core.agent_models.chat_on_worker") as chat:
            chat.return_value = valid
            self.assertEqual(verifier._action("worker_e2e", run_id)["status"], "pass")
            for bad in ({}, {**valid,"done":False}, {**valid,"model":"wrong"},
                        {**valid,"message":{"role":"assistant","content":"OK"}},
                        {**valid,"message":{"role":"assistant","content":"CORA_" + "b"*32}},
                        {**valid,"message":{"role":"assistant","content":""}},
                        {**valid,"message":{"role":"assistant","content":"CORA_"+run_id,"tool_calls":[{}]}}):
                with self.subTest(reply=bad):
                    chat.return_value = deepcopy(bad)
                    self.assertEqual(verifier._action("worker_e2e", run_id)["status"], "fail")

    def test_targeted_host_e2e_uses_authenticated_updater_snapshot(self):
        snapshot = {
            "os": {"ID": "debian", "VERSION_ID": "13"},
            "identity": {"uidMatchesConfigured": True, "privateUpdaterFiles": True},
            "packages": {
                "dpkg": {"available": True, "auditClean": True},
                "upgrades": {"available": True, "simulationOk": True, "pending": 0},
            },
            "systemd": {
                "cora-updater.service": {
                    "available": True, "loadState": "loaded", "activeState": "active",
                    "subState": "running", "execMainStatus": "0", "fragmentPresent": True,
                    "standardOutput": "journal", "standardError": "inherit",
                },
                "ssh.service": {
                    "available": True, "loadState": "loaded", "activeState": "active",
                    "subState": "running", "execMainStatus": "0", "fragmentPresent": True,
                    "standardOutput": "journal", "standardError": "inherit",
                },
            },
        }
        with patch("programmer_agent.releases.request", return_value=snapshot) as request:
            for check in ("debian_host_e2e", "systemd_host_e2e", "host_admin_e2e"):
                with self.subTest(check=check):
                    self.assertEqual(verifier._action(check, "a"*32)["status"], "pass")
        self.assertEqual(request.call_count, 3)
        self.assertTrue(all(call.args[:2] == ("GET", "/host/diagnostics") for call in request.call_args_list))

    def test_host_e2e_never_claims_green_when_updates_or_bridge_are_unknown(self):
        pending = {
            "os": {"ID": "debian"},
            "identity": {"uidMatchesConfigured": True, "privateUpdaterFiles": True},
            "packages": {
                "dpkg": {"available": True, "auditClean": True},
                "upgrades": {"available": True, "simulationOk": True, "pending": 2},
            },
            "systemd": {},
        }
        with patch("programmer_agent.releases.request", return_value=pending):
            result = verifier._action("debian_host_e2e", "a"*32)
        self.assertEqual(result["status"], "unknown")
        self.assertIn("2 aggiornamenti", result["detail"])
        with patch("programmer_agent.releases.request", side_effect=ValueError("offline")):
            result = verifier._action("systemd_host_e2e", "a"*32)
        self.assertEqual(result["status"], "unknown")

    def test_baked_revision_wins_and_malformed_identity_is_never_truncated(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(release_identity, "ROOT", Path(folder)), patch.dict(
            os.environ, {"CORA_GIT_COMMIT": "b"*40}
        ):
            marker = Path(folder)/".cora-revision"
            marker.write_text("a"*40)
            self.assertEqual(release_identity.revision(), "a"*40)
            marker.write_text("a"*40+"invalid")
            self.assertEqual(release_identity.revision(), "")


if __name__ == "__main__":
    unittest.main()
