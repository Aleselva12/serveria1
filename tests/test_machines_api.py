"""Tests for the deliberately non-executing first Machines phase."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from core import machines_api as machines


class MachinesTests(unittest.TestCase):
    def test_registration_is_persistent_and_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"CORA_MACHINES_REGISTRY_FILE": str(Path(root) / "machines.json")}, clear=False):
                candidate = machines.MachineRegistration(name="Desktop", fqdn="Desktop.tail7b83c3.ts.net")
                self.assertEqual(candidate.fqdn, "desktop.tail7b83c3.ts.net")
                saved = machines.add_machine(candidate)
                self.assertEqual(saved["name"], "Desktop")
                with patch.object(machines, "_probe", return_value=(True, [])), patch.object(machines, "_tailscale_devices", return_value=([], None, False)):
                    result = machines.list_machines()
                    self.assertEqual(len(result["machines"]), 2)
                    self.assertTrue(result["machines"][1]["worker_ready"])
                    self.assertEqual(result["machines"][1]["capabilities"], [])
                    self.assertFalse(result["execution_enabled"])
                with self.assertRaises(HTTPException) as conflict:
                    machines.add_machine(candidate)
                self.assertEqual(conflict.exception.status_code, 409)
                self.assertEqual(machines.delete_machine(saved["id"]), {"removed": True})
                self.assertEqual(machines._read(), [])

    def test_rejects_non_tailnet_or_malformed_hosts(self):
        for host in ("localhost", "127.0.0.1", "evil.com", "evil.ts.net@localhost",
                     "http://device.tailnet.ts.net", "device.tailnet.ts.net:443"):
            with self.subTest(host=host), self.assertRaises(ValidationError):
                machines.MachineRegistration(name="Worker", fqdn=host)

    def test_suffix_restricts_registration_to_our_tailnet(self):
        with patch.dict(os.environ, {"CORA_TAILSCALE_DNS_SUFFIX": "tail7b83c3.ts.net"}):
            machines.MachineRegistration(name="Test", fqdn="pc.tail7b83c3.ts.net")
            with self.assertRaises(ValidationError):
                machines.MachineRegistration(name="Test", fqdn="pc.another.ts.net")

    def test_inventory_list_does_not_promote_discovered_devices_to_worker(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"CORA_MACHINES_REGISTRY_FILE": str(Path(root) / "machines.json")}):
                discovered = [{"id": "123", "name": "laptop.tailnet.ts.net",
                               "fqdn": "laptop.tailnet.ts.net", "online": True}]
                with patch.object(machines, "_tailscale_devices", return_value=(discovered, None, True)):
                    response = machines.list_machines()
                laptop = response["machines"][1]
                self.assertEqual(laptop["type"], "tailnet_device")
                self.assertFalse(laptop["registered"])
                self.assertFalse(laptop["worker_ready"])


    def test_three_profiles_start_off_and_only_owner_settings_can_change(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"CORA_MACHINES_REGISTRY_FILE": str(Path(root) / "machines.json")}):
                saved = machines.add_machine(machines.MachineRegistration(
                    name="Desktop", fqdn="desktop.tail7b83c3.ts.net"))
                initial = machines._settings(saved)
                self.assertFalse(initial["enabled"])
                self.assertEqual(initial["active_profile"], "heavy")
                self.assertEqual(set(initial["profiles"]), {"heavy", "medium", "light"})
                with patch.object(machines, "_worker_call") as remote:
                    with self.assertRaises(HTTPException) as failure:
                        machines.test_worker_inference(saved["id"])
                    self.assertEqual(failure.exception.status_code, 409)
                    remote.assert_not_called()

                updated = machines.WorkerSettings(
                    enabled=True, active_profile="light",
                    profiles={"heavy": "gpt-oss:20b", "medium": "qwen3:8b-q8_0",
                              "light": "qwen3:4b-q8_0"},
                )
                machines.save_settings(saved["id"], updated)
                remote_responses = [
                    {"models": [{"name": "qwen3:4b-q8_0"}]},
                    {"model": "qwen3:4b-q8_0", "response": "CORA_WORKER_OK"},
                ]
                with patch.object(machines, "_worker_call", side_effect=remote_responses) as remote:
                    result = machines.test_worker_inference(saved["id"])
                self.assertEqual(result["response"], "CORA_WORKER_OK")
                self.assertEqual(remote.call_args.args[2]["model"], "qwen3:4b-q8_0")
                self.assertEqual(machines._find(saved["id"])["active_profile"], "light")
                with self.assertRaises(ValidationError):
                    machines.WorkerSettings(enabled=True, active_profile="heavy",
                                            profiles={"heavy": "ok", "medium": "ok"})

    def test_manual_model_selection_including_qwen_coder(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"CORA_MACHINES_REGISTRY_FILE": str(Path(root) / "machines.json")}):
                worker = machines.add_machine(machines.MachineRegistration(
                    name="Desktop", fqdn="desktop.tail7b83c3.ts.net"))
                # New machines have no automatic model chosen and start disabled.
                self.assertEqual(machines._settings(worker)["selected_model"], "")
                self.assertFalse(machines._settings(worker)["enabled"])
                models = {"heavy": "gpt-oss:20b", "medium": "qwen3:8b-q8_0",
                          "light": "qwen3:4b-q8_0"}
                coder = "qwen3-coder:30b-a3b-q4_K_M"
                settings = machines.WorkerSettings(enabled=True, active_profile="heavy",
                    profiles=models, selected_model=coder)
                saved = machines.save_settings(worker["id"], settings)
                self.assertEqual(saved["selected_model"], coder)
                replies = [{"models": [{"name": coder}, {"name": "qwen3:8b"}]},
                           {"model": coder, "response": "CORA_WORKER_OK"}]
                with patch.object(machines, "_worker_call", side_effect=replies) as call:
                    result = machines.test_worker_inference(worker["id"])
                self.assertEqual(result["model"], coder)
                self.assertEqual(call.call_args.args[2]["model"], coder)
                # Manually changing model never changes legacy profile assignments.
                newer = machines.WorkerSettings(enabled=True, active_profile="heavy",
                    profiles=models, selected_model="qwen3:8b")
                machines.save_settings(worker["id"], newer)
                self.assertEqual(machines._find(worker["id"])["profiles"], models)
                self.assertEqual(machines._settings(machines._find(worker["id"]))["selected_model"], "qwen3:8b")
                with patch.object(machines, "_worker_call", return_value={"models": [{"name": coder}]}):
                    with self.assertRaises(HTTPException) as error:
                        machines.generate(worker["id"], machines.InferencePrompt(prompt="test"))
                    self.assertEqual(error.exception.status_code, 409)

    def test_legacy_profile_selection_is_not_lost(self):
        legacy = {"enabled": True, "active_profile": "light",
                  "profiles": {"heavy": "large", "medium": "mid", "light": "small"}}
        self.assertEqual(machines._settings(legacy)["selected_model"], "small")
        self.assertEqual(machines._settings({"enabled": False})["selected_model"], "")

    def test_authenticated_worker_requests_require_exact_tailnet(self):
        with patch.dict(os.environ, {"CORA_WORKER_SHARED_TOKEN": "s" * 48,
                                     "CORA_TAILSCALE_DNS_SUFFIX": "tail7b83c3.ts.net"}):
            with self.assertRaises(HTTPException) as fail:
                machines._worker_call({"name": "Unknown", "fqdn": "someone.another.ts.net"},
                                      "/models")
            self.assertEqual(fail.exception.status_code, 503)
        with patch.dict(os.environ, {"CORA_WORKER_SHARED_TOKEN": "s" * 48,
                                     "CORA_TAILSCALE_DNS_SUFFIX": ""}):
            with self.assertRaises(HTTPException) as fail:
                machines._worker_call({"name": "Desktop", "fqdn": "pc.tail7b83c3.ts.net"},
                                      "/models")
            self.assertEqual(fail.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
