import json
import tempfile
import unittest
from pathlib import Path

from deploy.worker_updater_env import read_settings, synchronize


class WorkerUpdaterEnvTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "updater"
        self.root.mkdir()
        self.env = Path(self.tmp.name) / "deploy.env"
        self.token = "1" * 64
        self.env.write_text("CORA_WORKER_SHARED_TOKEN=" + self.token +
                            "\nCORA_TAILSCALE_DNS_SUFFIX=tail7b83c3.ts.net\n")
        self.snapshot = self.root / "compose.json"
        self.original = {"name": "cora", "services": {
            "api": {"environment": {"CORA_POSTGRES_PASSWORD": "secret"},
                    "volumes": ["/keep-this-volume:/state"]},
            "web": {"ports": ["127.0.0.1:8080:80"]}}}
        self.snapshot.write_text(json.dumps(self.original))

    def tearDown(self):
        self.tmp.cleanup()

    def test_check_is_readonly(self):
        change, backup = synchronize(self.root, self.env)
        self.assertTrue(change)
        self.assertIsNone(backup)
        self.assertEqual(json.loads(self.snapshot.read_text()), self.original)

    def test_apply_preserves_all_other_services_and_creates_private_backup(self):
        change, backup = synchronize(self.root, self.env, apply=True)
        self.assertTrue(change)
        self.assertIsNotNone(backup)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(backup.read_text()), self.original)
        after = json.loads(self.snapshot.read_text())
        self.assertEqual(after["services"]["web"], self.original["services"]["web"])
        self.assertEqual(after["services"]["api"]["volumes"], self.original["services"]["api"]["volumes"])
        self.assertEqual(after["services"]["api"]["environment"]["CORA_POSTGRES_PASSWORD"], "secret")
        self.assertEqual(after["services"]["api"]["environment"]["CORA_WORKER_SHARED_TOKEN"], self.token)
        self.assertEqual(after["services"]["api"]["environment"]["CORA_TAILSCALE_DNS_SUFFIX"], "tail7b83c3.ts.net")
        self.assertEqual(self.snapshot.stat().st_mode & 0o777, 0o600)
        changed_again, other_backup = synchronize(self.root, self.env, apply=True)
        self.assertFalse(changed_again)
        self.assertIsNone(other_backup)

    def test_rejects_incomplete_and_duplicate_private_settings(self):
        self.env.write_text("CORA_WORKER_SHARED_TOKEN=short\nCORA_TAILSCALE_DNS_SUFFIX=other.ts.net\n")
        with self.assertRaises(ValueError):
            read_settings(self.env)
        self.env.write_text("CORA_WORKER_SHARED_TOKEN=" + self.token +
                            "\nCORA_WORKER_SHARED_TOKEN=" + self.token +
                            "\nCORA_TAILSCALE_DNS_SUFFIX=tail7b83c3.ts.net\n")
        with self.assertRaises(ValueError):
            synchronize(self.root, self.env, apply=True)
        self.assertEqual(json.loads(self.snapshot.read_text()), self.original)


if __name__ == "__main__":
    unittest.main()
