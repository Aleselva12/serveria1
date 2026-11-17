"""W3 scheduler: per-check periods and the nightly collaudo window."""
import os
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from core.health_catalog import CATALOG
from core.verify import node_verification as nv
from core.verify import project_checks as pc


class PeriodicScheduleTests(unittest.TestCase):
    def test_service_reachability_runs_every_15_minutes_and_preflights_every_5(self):
        for key in ("immich_e2e", "nextcloud_e2e"):
            self.assertEqual((CATALOG[key]["automated"], CATALOG[key]["intervalSeconds"]), (True, 900))
            self.assertIn(key, pc._PROBES)
        self.assertEqual(CATALOG["database"]["intervalSeconds"], 300)
        self.assertEqual(CATALOG["database"]["maxAgeSeconds"], 600)
        self.assertIsNone(CATALOG["memory_regression"]["intervalSeconds"])
        self.assertGreater(CATALOG["memory_regression"]["maxAgeSeconds"], 24 * 3600)

    def test_only_checks_whose_period_elapsed_are_due(self):
        now = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
        seen = {key: now - timedelta(minutes=6) for key in pc._PROBES}
        seen["immich_e2e"] = now - timedelta(minutes=6)
        seen["nextcloud_e2e"] = now - timedelta(minutes=16)
        due = pc.due_checks(seen, now)
        self.assertIn("database", due)
        self.assertNotIn("immich_e2e", due)
        self.assertIn("nextcloud_e2e", due)
        # A check that ran a few seconds early last tick is not skipped for a whole period.
        self.assertIn("database", pc.due_checks({"database": now - timedelta(seconds=290)}, now))
        self.assertNotIn("database", pc.due_checks({**seen, "database": now - timedelta(seconds=60)}, now))
        self.assertEqual(pc.due_checks({}, now), set(pc._PROBES))

    def test_a_partial_cycle_keeps_the_other_results_in_the_snapshot(self):
        probes = {"database": lambda: ("pass", "ok"), "library": lambda: ("fail", "giù")}
        with patch.dict(pc._PROBES, probes, clear=True), patch.object(pc, "_LAST", None):
            pc.run_once(due={"database", "library"})
            pc._PROBES["database"] = lambda: ("warn", "lento")
            snap = pc.run_once(due={"database"})
        self.assertEqual({c["id"]: c["status"] for c in snap["checks"]}, {"database": "warn", "library": "fail"})

    def test_without_a_database_the_process_keeps_each_period(self):
        calls = []
        with patch.dict(pc._PROBES, {"database": lambda: calls.append(1) or ("pass", "ok")}, clear=True), \
                patch.object(pc, "_LAST", None), patch.dict(pc._MEMORY_LAST, {}, clear=True), \
                patch("core.infra.database.DATABASE_URL", ""):
            pc._scheduled_cycle()
            pc._scheduled_cycle()
        self.assertEqual(len(calls), 1)


class NightlyTests(unittest.TestCase):
    def at(self, hour, minute=10):
        # 17/11/2026 is CET (UTC+1): local hour h is UTC h-1.
        return datetime(2026, 11, 17, hour - 1, minute, tzinfo=UTC)

    def test_offline_machines_are_skipped_never_woken(self):
        targets = {"desktopMachineId": "d", "laptopMachineId": "l"}
        available = ["database", "desktop_e2e", "laptop_e2e", "memory_regression"]
        reachable, checks = nv.nightly_plan(targets, available, online=lambda machine: machine == "d")
        self.assertEqual(reachable, {"desktopMachineId": "d"})
        self.assertEqual(checks, ["database", "desktop_e2e", "memory_regression"])
        reachable, checks = nv.nightly_plan({}, available, online=lambda machine: True)
        self.assertEqual((reachable, checks), ({}, ["database", "memory_regression"]))

    @contextmanager
    def server(self, already_ran=False):
        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = [({"x": 1} if already_ran else None), None]
        @contextmanager
        def connection():
            yield conn
        with patch.object(nv, "_connection", connection), \
                patch.object(nv, "_installed_release", return_value="a" * 40), \
                patch("core.verify.project_checks._environment", return_value="debian-api"), \
                patch.object(nv.verify_nodes, "available_checks", return_value=("database", "desktop_e2e")), \
                patch.object(nv, "_launch") as launch, patch.dict(os.environ, {"CORA_NIGHTLY_VERIFY": "1"}):
            yield launch

    def test_runs_once_inside_the_4_to_5_window(self):
        with self.server() as launch:
            self.assertEqual(nv.nightly_verify(self.at(3, 59)), "outside_window")
            self.assertEqual(nv.nightly_verify(self.at(5, 0)), "outside_window")
            self.assertEqual(nv.nightly_verify(self.at(4, 0)), "started")
        body, trigger, checks = launch.call_args.args
        self.assertEqual((trigger, checks), ("nightly", ["database"]))
        with self.server(already_ran=True) as launch:
            self.assertEqual(nv.nightly_verify(self.at(4, 30)), "already_ran")
            launch.assert_not_called()

    def test_a_busy_lock_is_retried_and_can_be_disabled(self):
        with self.server() as launch:
            launch.side_effect = nv.HTTPException(409, "busy")
            self.assertEqual(nv.nightly_verify(self.at(4)), "busy")
        with patch.dict(os.environ, {"CORA_NIGHTLY_VERIFY": "0"}):
            self.assertEqual(nv.nightly_verify(self.at(4)), "disabled")

    def test_launch_restricts_the_suite_and_labels_the_trigger(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {"acquired": True}
        with patch.object(nv, "_connection", return_value=conn), \
                patch.object(nv.verify_nodes, "available_checks", return_value=("a", "b", "c")), \
                patch.object(nv, "Thread") as thread:
            job = nv._launch(None, "nightly", ["c", "a", "zzz"])
        self.assertEqual(job["checks"], ["a", "c"])
        self.assertEqual(job["trigger"], "nightly")
        self.assertIn("notturno", job["detail"])
        thread.return_value.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
