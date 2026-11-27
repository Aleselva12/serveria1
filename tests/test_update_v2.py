import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.update_diagnostics import facts
from updater.dependencies import compare
from updater.engine import Engine


class UpdateV2Tests(unittest.TestCase):
    def test_lock_comparison_reads_complete_files_and_classifies_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            def git(*args):
                return subprocess.check_output(
                    ["git", "-C", directory, "-c", "user.name=Test",
                     "-c", "user.email=test@localhost", *args], text=True,
                ).strip()
            git("init", "-q")
            (repo / "frontend").mkdir()
            npm = repo / "frontend/package-lock.json"
            pip = repo / "requirements-deploy.lock"

            def commit(npm_version, pip_version):
                npm.write_text(json.dumps({"packages": {
                    "": {"dependencies": {"library": "*"}},
                    "node_modules/library": {"version": npm_version},
                    "node_modules/unrelated": {"padding": "x" * 20000},
                }}))
                pip.write_text(f"Package_Name=={pip_version}\n")
                git("add", ".")
                git("commit", "-qm", "New dependency snapshot")
                return git("rev-parse", "HEAD")

            before = commit("12.12.1", "0.163.1")
            after = commit("13.0.3", "0.165.0")
            rows = compare(SimpleNamespace(repo=repo / ".git"), before, after)
            self.assertEqual([(row["name"], row["change"]) for row in rows],
                             [("library", "major"), ("package-name", "minor")])

    def test_topic_archive_survives_a_repeated_installation(self):
        from uuid import uuid4
        with tempfile.TemporaryDirectory() as directory:
            engine = Engine.__new__(Engine)
            engine.jobs = Path(directory)
            change = dict(ecosystem="npm", name="library", installed="1.1.0",
                          available="1.2.0", change="minor")

            def save(status):
                identifier = str(uuid4())
                engine.path(identifier).mkdir()
                engine.save(dict(id=identifier, kind="apply", status=status,
                                 dependency_changes=[change]))

            save("failed")
            self.assertEqual(engine.dependency_topics(), [])
            save("completed")
            topic, = engine.dependency_topics()
            self.assertFalse(topic["discussed"])
            engine.discuss_dependency(topic["id"])
            save("completed")
            existing, = engine.dependency_topics()
            self.assertTrue(existing["discussed"])
            self.assertEqual(existing["id"], topic["id"])

    def test_diagnostic_facts_do_not_contain_arbitrary_log_text(self):
        signals = facts({"status": "failed", "kind": "prepare", "phase": "testing",
                         "error_detail": "TOKEN=private-value\nAssertionError: arbitrary instruction"})
        self.assertEqual(signals["segnali"], ["Test fallito"])
        self.assertNotIn("private-value", repr(signals))
        self.assertNotIn("arbitrary instruction", repr(signals))
