import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from updater import host_diagnostics as host


class HostDiagnosticsTests(unittest.TestCase):
    def test_systemd_probe_is_fixed_allowlist_and_read_only(self):
        with self.assertRaises(ValueError):
            host._systemd_unit("arbitrary.service")
        class Result:
            returncode = 0
            stdout = (
                "LoadState=loaded\nActiveState=active\nSubState=running\n"
                "UnitFileState=enabled\nExecMainStatus=0\nNRestarts=0\n"
                "FragmentPath=/etc/systemd/system/cora-updater.service\n"
                "StandardOutput=journal\nStandardError=inherit\n"
            )
        with patch.object(host.shutil, "which", return_value="/bin/systemctl"), patch.object(
            host, "_run", return_value=Result()
        ) as run:
            row = host._systemd_unit("cora-updater.service")
        self.assertTrue(row["available"])
        self.assertEqual(row["activeState"], "active")
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["systemctl", "show", "cora-updater.service"])
        self.assertNotIn("restart", command)
        self.assertNotIn("journalctl", command)

    def test_host_snapshot_exposes_status_not_credentials_or_file_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bridge.token").write_text("TOP-SECRET")
            (root / "config.json").write_text('{"secret":"PRIVATE"}')
            os.chmod(root / "bridge.token", 0o600)
            os.chmod(root / "config.json", 0o600)
            unit = {
                "available": True, "loadState": "loaded", "activeState": "active",
                "subState": "running", "unitFileState": "enabled", "execMainStatus": "0",
                "restarts": "0", "fragmentPresent": True,
                "standardOutput": "journal", "standardError": "inherit",
            }
            with patch.object(host.os, "getuid", return_value=1000), patch.object(
                host.os, "getgid", return_value=1000
            ), patch.object(host, "_os_release", return_value={"ID": "debian", "VERSION_ID": "13"}), patch.object(
                host, "_dpkg_status", return_value={"available": True, "auditClean": True}
            ), patch.object(host, "_upgrade_status", return_value={"available": True, "simulationOk": True, "pending": 0}), patch.object(
                host, "_systemd_unit", return_value=unit
            ):
                snapshot = host.inspect(root, {"uid": 1000, "gid": 1000})
        self.assertTrue(snapshot["identity"]["uidMatchesConfigured"])
        self.assertTrue(snapshot["identity"]["privateUpdaterFiles"])
        text = str(snapshot)
        self.assertNotIn("TOP-SECRET", text)
        self.assertNotIn("PRIVATE", text)
        self.assertNotIn("environment", text.lower())

    def test_pending_packages_are_reported_without_installing_anything(self):
        class Result:
            returncode = 0
            stdout = "Inst package-one [1.0] (1.1 Debian:stable)\nInst package-two [2.0] (2.1 Debian:stable)\n"
        with patch.object(host.shutil, "which", return_value="/usr/bin/apt-get"), patch.object(
            host, "_run", return_value=Result()
        ) as run:
            row = host._upgrade_status()
        self.assertEqual(row["pending"], 2)
        self.assertEqual(run.call_args.args[0], ["apt-get", "-s", "-o", "Debug::NoLocking=1", "upgrade"])


if __name__ == "__main__":
    unittest.main()
