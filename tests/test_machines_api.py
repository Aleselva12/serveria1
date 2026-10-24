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


if __name__ == "__main__":
    unittest.main()
