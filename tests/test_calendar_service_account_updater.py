"""No-live-server regression tests for Calendar updater configuration."""
import json
import tempfile
import unittest
from pathlib import Path

from deploy.calendar_service_account_updater import configure, apply, read_calendar_id


class CalendarUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.updater = self.root / "updater"
        self.updater.mkdir()
        (self.updater / "jobs").mkdir()
        self.env = self.root / "deploy.env"
        self.env.write_text("CORA_GOOGLE_CALENDAR_ID=owner@example.com\n")
        self.key = self.root / "key.json"
        self.key.write_text(json.dumps({
            "type": "service_account",
            "client_email": "bot@example.iam.gserviceaccount.com",
            "private_key": "synthetic-not-a-real-key",
        }))
        self.key.chmod(0o600)
        self.base = {"name": "cora", "services": {
            "api": {"environment": {"OTHER": "keep"},
                    "volumes": [{"type": "bind", "source": "/state", "target": "/state"}]},
            "web": {"environment": {"KEEP": "yes"}},
            "terminal": {"image": "local"},
        }}
        (self.updater / "compose.json").write_text(json.dumps(self.base))
        (self.updater / "images.json").write_text(json.dumps({"services": {"api": {"image": "sha256:old"}}}))

    def test_reconcile_preserves_other_services_and_is_idempotent(self):
        first = configure(self.base, source=str(self.key), calendar_id="owner@example.com")
        self.assertEqual(first["services"]["terminal"], self.base["services"]["terminal"])
        self.assertEqual(first["services"]["api"]["environment"]["OTHER"], "keep")
        self.assertEqual(first["services"]["api"]["environment"]["CORA_GOOGLE_CALENDAR_ID"], "owner@example.com")
        mount = next(x for x in first["services"]["api"]["volumes"] if x["target"].endswith("cora-calendar.json"))
        self.assertTrue(mount["read_only"])
        self.assertEqual(configure(first, source=str(self.key), calendar_id="owner@example.com"), first)
        self.assertNotIn("CORA_GOOGLE_CALENDAR_ID", self.base["services"]["api"]["environment"])

    def test_rejects_conflicting_mount(self):
        configured = configure(self.base, source=str(self.key), calendar_id="owner@example.com")
        with self.assertRaises(ValueError):
            configure(configured, source="/different/key.json", calendar_id="owner@example.com")

    def test_apply_creates_backup_and_preserves_images(self):
        original = (self.updater / "compose.json").read_bytes()
        image_original = (self.updater / "images.json").read_bytes()
        backup = apply(self.updater, self.env, self.key, verify=False)
        self.assertEqual(Path(backup).read_bytes(), original)
        self.assertEqual((self.updater / "images.json").read_bytes(), image_original)
        self.assertEqual(apply(self.updater, self.env, self.key, verify=False), "already-configured")

    def test_rejects_busy_updater(self):
        job = self.updater / "jobs" / "123"
        job.mkdir()
        (job / "job.json").write_text('{"status":"recovery_required"}')
        with self.assertRaises(ValueError):
            apply(self.updater, self.env, self.key, verify=False)

    def test_rejects_url_instead_of_calendar_id(self):
        self.env.write_text("CORA_GOOGLE_CALENDAR_ID=https://calendar.google.com/calendar/embed?src=x\n")
        with self.assertRaises(ValueError):
            read_calendar_id(self.env)


if __name__ == "__main__":
    unittest.main()
