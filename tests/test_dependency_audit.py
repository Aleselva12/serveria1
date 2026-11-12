import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core import additional_verifications as checks
from updater import host_diagnostics as host


class FakeOSV:
    """Answers like api.osv.dev without network: package -> [(id, severity)]."""
    def __init__(self, data, fail=False):
        self.data, self.fail, self.sent = data, fail, []

    def post(self, url, json):
        if self.fail:
            raise OSError("offline")
        self.sent.append(json)
        results = [{"vulns": [{"id": vid} for vid, _ in self.data.get(q["package"]["name"], [])]} for q in json["queries"]]
        return MagicMock(json=lambda: {"results": results}, raise_for_status=lambda: None)

    def get(self, url):
        vid = url.rsplit("/", 1)[1]
        level = next(s for items in self.data.values() for i, s in items if i == vid)
        body = {"id": vid, "database_specific": {"severity": level} if level else {}}
        return MagicMock(json=lambda: body, raise_for_status=lambda: None)


class DependencyAuditTests(unittest.TestCase):
    PACKAGES = [("certifi", "2026.7.22"), ("httpx", "0.28.1")]

    def test_clean_moderate_and_high_map_to_pass_warn_fail(self):
        state, detail = checks.dependency_audit(self.PACKAGES, FakeOSV({}))
        self.assertEqual(state, "pass")
        self.assertIn("2 pacchetti", detail)
        state, detail = checks.dependency_audit(self.PACKAGES, FakeOSV({"httpx": [("GHSA-a", "MODERATE")]}))
        self.assertEqual((state, "httpx 0.28.1" in detail), ("warn", True))
        state, detail = checks.dependency_audit(self.PACKAGES, FakeOSV({"httpx": [("GHSA-a", "LOW")], "certifi": [("GHSA-b", "LOW"), ("GHSA-c", "CRITICAL")]}))
        self.assertEqual(state, "fail")
        self.assertIn("certifi 2026.7.22", detail)
        self.assertNotIn("httpx", detail)

    def test_unknown_severity_is_not_safe_and_offline_is_not_a_pass(self):
        self.assertEqual(checks.dependency_audit(self.PACKAGES, FakeOSV({"httpx": [("PYSEC-x", None)]}))[0], "warn")
        self.assertEqual(checks.dependency_audit(self.PACKAGES, FakeOSV({}, fail=True))[0], "unknown")
        self.assertEqual(checks.dependency_audit([], FakeOSV({}))[0], "unknown")

    def test_only_names_and_versions_are_sent(self):
        osv = FakeOSV({})
        checks.dependency_audit(self.PACKAGES, osv)
        query = osv.sent[0]["queries"][0]
        self.assertEqual(query, {"package": {"name": "certifi", "ecosystem": "PyPI"}, "version": "2026.7.22"})

    def test_registered_in_catalog_runner_and_tree(self):
        from core.health_catalog import CATALOG
        from deploy.verify_nodes import available_checks
        self.assertIn("dependency_audit", available_checks())
        self.assertTrue(CATALOG["dependency_audit"]["releaseScoped"])
        self.assertFalse(CATALOG["database"]["releaseScoped"])
        model = (Path(__file__).resolve().parents[1] / "frontend/src/tree/model.ts").read_text(encoding="utf-8")
        self.assertIn('"R5.2.p2":["dependency_audit"', model)


class AutoSecurityUpdateTests(unittest.TestCase):
    def _flags(self, content, installed=True):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "20auto-upgrades").write_text(content, encoding="utf-8")
            with patch.object(host.shutil, "which", return_value="/usr/bin/unattended-upgrade" if installed else None):
                return host._auto_security_updates(Path(folder))

    def test_enabled_disabled_commented_and_missing(self):
        self.assertEqual(self._flags('APT::Periodic::Unattended-Upgrade "1";\n'), {"installed": True, "enabled": True})
        self.assertFalse(self._flags('APT::Periodic::Unattended-Upgrade "0";\n')["enabled"])
        self.assertFalse(self._flags('// APT::Periodic::Unattended-Upgrade "1";\n')["enabled"])
        self.assertFalse(self._flags('APT::Periodic::Unattended-Upgrade "1";\n', installed=False)["installed"])
        self.assertEqual(host._auto_security_updates(Path("/nonexistent-cora")), {"installed": host.shutil.which("unattended-upgrade") is not None, "enabled": False})

    def test_debian_check_warns_until_automatic_security_updates_are_on(self):
        from deploy import verify_nodes as verifier
        def snapshot(auto, pending=0):
            packages = {"dpkg": {"available": True, "auditClean": True},
                        "upgrades": {"available": True, "simulationOk": True, "pending": pending}}
            if auto is not None:
                packages["autoSecurityUpdates"] = auto
            return {"os": {"ID": "debian"}, "identity": {"uidMatchesConfigured": True, "privateUpdaterFiles": True},
                    "packages": packages, "systemd": {}}
        cases = (({"installed": True, "enabled": True}, "pass"), ({"installed": True, "enabled": False}, "warn"),
                 ({"installed": False, "enabled": False}, "warn"), (None, "pass"))
        for auto, expected in cases:
            with patch("programmer_agent.releases.request", return_value=snapshot(auto)):
                result = verifier._action("debian_host_e2e", "a" * 32)
            self.assertEqual(result["status"], expected, auto)
        with patch("programmer_agent.releases.request", return_value=snapshot({"installed": False, "enabled": False}, pending=3)):
            detail = verifier._action("debian_host_e2e", "a" * 32)["detail"]
        self.assertIn("3 aggiornamenti", detail)
        self.assertIn("unattended-upgrades", detail)
