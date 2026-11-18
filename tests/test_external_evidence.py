"""CI GitHub and updater outcomes recorded as information only."""
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from core.verify import external_evidence as ee

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def run(name, conclusion="success", status="completed"):
    return {"name": name, "status": status, "conclusion": conclusion}


class SummaryTests(unittest.TestCase):
    def test_check_runs(self):
        self.assertEqual(ee.summarize_check_runs([run("lint"), run("CodeQL", "skipped")])[0], "pass")
        status, detail = ee.summarize_check_runs([run("lint"), run("deployment", "failure"), run("x", "timed_out")])
        self.assertEqual(status, "fail")
        self.assertIn("deployment", detail)
        self.assertEqual(ee.summarize_check_runs([run("lint"), run("build", None, "in_progress")])[0], "unknown")
        self.assertEqual(ee.summarize_check_runs([])[0], "unknown")

    def test_github_errors_are_unknown_not_failures(self):
        def broken(url):
            raise OSError("rete")
        self.assertEqual(ee.ci_evidence("a" * 40, fetch=broken), ("unknown", "CI GitHub non raggiungibile: OSError"))
        seen = []
        ee.ci_evidence("b" * 40, fetch=lambda url: seen.append(url) or {"check_runs": []})
        self.assertEqual(seen, [f"https://api.github.com/repos/Aleselva12/serveria1/commits/{'b' * 40}/check-runs?per_page=100"])

    def test_latest_installation_or_rollback_wins(self):
        jobs = [
            {"kind": "apply", "status": "completed", "commit": "a" * 40, "updated_at": "2026-11-17T08:00:00"},
            {"kind": "prepare", "status": "failed", "commit": "c" * 40, "updated_at": "2026-11-17T11:00:00"},
            {"kind": "apply", "status": "failed", "commit": "b" * 40, "updated_at": "2026-11-17T10:00:00", "error_stage": "health"},
        ]
        status, detail, commit = ee.updater_evidence(jobs)
        self.assertEqual((status, commit), ("fail", "b" * 40))
        self.assertIn("fase health", detail)
        self.assertIn("versione precedente mantenuta", detail)
        status, detail, _ = ee.updater_evidence(jobs[:1])
        self.assertEqual(status, "pass")
        self.assertIn("installazione di aaaaaaa completata (2026-11-17 08:00 UTC)", detail)
        self.assertEqual(ee.updater_evidence([{"kind": "apply", "status": "recovery_required", "commit": "d" * 40}])[0], "fail")
        self.assertEqual(ee.updater_evidence([])[0], "unknown")

    def test_rows_are_written_only_on_change_or_once_a_day(self):
        row = {"status": "pass", "detail": "ok", "commit": "a"}
        previous = {"status": "pass", "detail": "ok", "commit_sha": "a", "observed_at": NOW - timedelta(hours=2)}
        self.assertFalse(ee.changed(previous, row, NOW))
        self.assertTrue(ee.changed({**previous, "status": "fail"}, row, NOW))
        self.assertTrue(ee.changed({**previous, "commit_sha": "b"}, row, NOW))
        self.assertTrue(ee.changed({**previous, "observed_at": NOW - timedelta(hours=25)}, row, NOW))
        self.assertTrue(ee.changed(None, row, NOW))


class RecordTests(unittest.TestCase):
    def record(self, environment="debian-api", previous=None):
        conn = MagicMock()
        def execute(sql, params=()):
            result = MagicMock()
            result.fetchone.return_value = {"ok": True} if "advisory" in sql else previous
            return result
        conn.execute.side_effect = execute
        @contextmanager
        def connect():
            yield conn
        rows = [{"id": "ci_github", "status": "pass", "detail": "ok", "commit": "a" * 40},
                {"id": "updater_install", "status": "fail", "detail": "ko", "commit": "a" * 40}]
        with patch("core.infra.database.db_connection", connect), \
                patch("core.verify.project_checks._environment", return_value=environment), \
                patch("core.verify.project_checks._release", return_value="a" * 40), \
                patch.object(ee, "collect", return_value=rows):
            written = ee.record(NOW)
        inserts = [c.args[1] for c in conn.execute.call_args_list if "INSERT INTO project_health_results" in c.args[0]]
        return written, inserts

    def test_information_is_stored_with_its_own_source_and_environment(self):
        written, inserts = self.record()
        self.assertEqual(written, 2)
        self.assertEqual([(i[0], i[3], i[4]) for i in inserts],
                         [("ci_github", "ci", "ci-github"), ("updater_install", "updater", "updater-host")])
        # Not Debian evidence: the map only counts environments starting with "debian".
        self.assertFalse(any(i[4].startswith("debian") for i in inserts))

    def test_only_the_installed_server_records(self):
        self.assertEqual(self.record(environment="ci-api"), (0, []))

    def test_unchanged_outcomes_are_not_repeated(self):
        previous = {"status": "pass", "detail": "ok", "commit_sha": "a" * 40, "observed_at": NOW - timedelta(minutes=5)}
        written, inserts = self.record(previous=previous)
        self.assertEqual([i[0] for i in inserts], ["updater_install"])


if __name__ == "__main__":
    unittest.main()
