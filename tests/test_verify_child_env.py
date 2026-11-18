"""Nightly regression suites must not inherit the live server environment."""
import os
import unittest
from unittest.mock import patch

from deploy import verify_nodes as verifier

LIVE = {"PATH": "/usr/bin", "HOME": "/root", "LC_ALL": "C.UTF-8", "PYTHONUNBUFFERED": "1",
        "CORA_DATABASE_URL": "postgresql://real", "POSTGRES_PASSWORD": "x", "CORA_MODEL": "qwen3:8b",
        "CORA_GOOGLE_CALENDAR_TOKEN_PATH": "/state/token.json", "CORA_VERIFICATION_SYNTHETIC": "0"}


class ChildEnvTests(unittest.TestCase):
    def test_regression_children_get_only_a_clean_environment(self):
        action = next(iter(verifier.REGRESSIONS))
        with patch.dict(os.environ, LIVE, clear=True):
            env = verifier._child_env(action, {"CORA_EXTRA": "1"})
        self.assertEqual(env, {"PATH": "/usr/bin", "HOME": "/root", "LC_ALL": "C.UTF-8", "PYTHONUNBUFFERED": "1",
                               "CORA_EMBEDDING_MODEL": "", "CORA_VERIFICATION_SYNTHETIC": "1"})

    def test_every_tree_regression_suite_is_scrubbed(self):
        with patch.dict(os.environ, LIVE, clear=True):
            for action in verifier.REGRESSIONS:
                self.assertNotIn("CORA_DATABASE_URL", verifier._child_env(action), action)

    def test_live_checks_keep_the_server_environment(self):
        with patch.dict(os.environ, LIVE, clear=True):
            env = verifier._child_env("memory_write", {"CORA_EXTRA": "1"})
        self.assertEqual(env["CORA_DATABASE_URL"], "postgresql://real")
        self.assertEqual(env["CORA_EXTRA"], "1")
        self.assertEqual(env["CORA_VERIFICATION_SYNTHETIC"], "0")


if __name__ == "__main__":
    unittest.main()
