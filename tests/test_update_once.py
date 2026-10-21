"""Regression tests for the owner-requested, single-command updater flow."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from deploy import update_once


COMMIT = "a" * 40
ACTIVE = "b" * 40


class UpdateOnceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config.json").write_text(json.dumps({"api_target": "api-audio-cpu"}))

    def test_verified_release_precedes_single_apply(self):
        responses = iter([
            {"available": True, "active_commit": ACTIVE, "jobs": []},
            {"id": "workspace1", "source_commit": COMMIT},
            {"commit": COMMIT},
            {"id": "prepare1"},
            {"kind": "prepare", "status": "ready", "commit": COMMIT, "phase": "ready"},
            {"id": "apply1"},
            {"kind": "apply", "status": "completed", "commit": COMMIT, "phase": "completed"},
            {"active_commit": COMMIT}
        ])
        with patch.object(update_once, "api", side_effect=lambda *a, **k: next(responses)) as request:
            update_once.run(self.root, COMMIT)
        calls = [(call.args[1], call.args[2]) for call in request.call_args_list]
        self.assertEqual(calls, [
            ("GET", "/status"), ("POST", "/workspaces"),
            ("POST", "/workspaces/workspace1/commit"),
            ("POST", "/jobs"), ("GET", "/jobs/prepare1"),
            ("POST", "/jobs"), ("GET", "/jobs/apply1"), ("GET", "/status")
        ])

    def test_wrong_remote_commit_never_starts_job(self):
        with patch.object(update_once, "api", side_effect=[
            {"available": True, "active_commit": ACTIVE, "jobs": []},
            {"id": "workspace1", "source_commit": "c" * 40}
        ]) as request:
            with self.assertRaisesRegex(RuntimeError, "GitHub main differisce"):
                update_once.run(self.root, COMMIT)
        self.assertEqual(request.call_count, 2)

    def test_conflicting_active_job_never_starts_work(self):
        with patch.object(update_once, "api", return_value={
            "available": True, "jobs": [{"status": "recovery_required"}]
        }) as request:
            with self.assertRaisesRegex(RuntimeError, "già presente"):
                update_once.run(self.root, COMMIT)
        request.assert_called_once()

    def test_audio_target_is_required_before_any_api_call(self):
        (self.root / "config.json").write_text(json.dumps({"api_target": "api"}))
        with patch.object(update_once, "api") as request:
            with self.assertRaisesRegex(RuntimeError, "api-audio-cpu"):
                update_once.run(self.root, COMMIT)
        request.assert_not_called()

    def test_failed_preparation_never_applies(self):
        responses = iter([
            {"available": True, "active_commit": ACTIVE, "jobs": []},
            {"id": "workspace1", "source_commit": COMMIT},
            {"commit": COMMIT},
            {"id": "prepare1"},
            {"kind": "prepare", "status": "failed", "commit": COMMIT, "error": "tests failed"}
        ])
        with patch.object(update_once, "api", side_effect=lambda *a, **k: next(responses)) as request:
            with self.assertRaisesRegex(RuntimeError, "tests failed"):
                update_once.run(self.root, COMMIT)
        jobs = [call for call in request.call_args_list if call.args[1:3] == ("POST", "/jobs")]
        self.assertEqual(len(jobs), 1)


if __name__ == "__main__":
    unittest.main()
