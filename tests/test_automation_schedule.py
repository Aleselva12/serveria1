import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.domain import automation_drafts as drafts
from core.domain import automation_runs as runs
from core.domain import automation_schedule as schedule

ROME = ZoneInfo("Europe/Rome")
BINDINGS = {"t.py:read": {"capability": "read:cap", "contract_id": "a.read", "effect": "read", "actor": "agent", "input_schema": {}}}


def flow(config):
    return {"title": "Mattina", "description": "", "nodes": [
        dict(id="start", kind="trigger", label="Avvio", x=10, y=10, config=config),
        dict(id="read", kind="tool", label="Leggi", x=200, y=10, tool_id="t.py:read", config={"q": "{{input.topic}}"}),
        dict(id="end", kind="output", label="Fine", x=400, y=10, config={}),
    ], "edges": [dict(id="a", source="start", target="read", label=""), dict(id="b", source="read", target="end", label="")]}


ON = {"schedule": {"enabled": True, "time": "08:00", "days": [0, 1, 2, 3, 4], "mode": "dry_run"}, "input": {"topic": "server"}}
MONDAY_0803 = datetime(2026, 11, 23, 8, 3, tzinfo=ROME)


class ScheduleRules(unittest.TestCase):
    def test_validation_reports_owner_facing_problems(self):
        self.assertEqual(schedule.schedule_problems({}), [])
        self.assertEqual(schedule.schedule_problems(ON), [])
        bad = schedule.schedule_problems({"schedule": {"enabled": "yes", "time": "8", "days": [7, True], "mode": "x"}, "input": []})
        self.assertEqual(len(bad), 5)

    def test_disabled_or_invalid_schedules_never_run(self):
        self.assertIsNone(schedule.schedule_of(flow({})))
        self.assertIsNone(schedule.schedule_of(flow({"schedule": {**ON["schedule"], "enabled": False}})))
        self.assertIsNone(schedule.schedule_of(flow({"schedule": {**ON["schedule"], "time": "25:00"}})))
        found = schedule.schedule_of(flow(ON))
        self.assertEqual((found["hour"], found["minute"], found["mode"], found["input"]), (8, 0, "dry_run", {"topic": "server"}))

    def test_slot_window_days_and_catch_up_limit(self):
        s = schedule.schedule_of(flow(ON))
        self.assertEqual(schedule.due_slot(s, MONDAY_0803), "2026-11-23 08:00")
        self.assertIsNone(schedule.due_slot(s, MONDAY_0803.replace(hour=7, minute=59)))
        self.assertIsNone(schedule.due_slot(s, MONDAY_0803.replace(minute=11)), "missed slots are not replayed")
        self.assertIsNone(schedule.due_slot(s, datetime(2026, 11, 28, 8, 1, tzinfo=ROME)), "Saturday is not selected")
        self.assertEqual(schedule.next_start(s, datetime(2026, 11, 27, 9, 0, tzinfo=ROME)).day, 30)

    def test_drafts_warn_about_a_broken_schedule(self):
        warnings = drafts.validate_graph(flow({"schedule": {"enabled": True, "time": "nope"}}))["warnings"]
        self.assertTrue(any("orario della pianificazione" in w for w in warnings))


class SchedulerTicks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.drafts, self.runs = Path(self.tmp.name, "d"), Path(self.tmp.name, "r")

    def tearDown(self):
        self.tmp.cleanup()

    def tick(self, now=MONDAY_0803):
        return schedule.tick(now, bindings=BINDINGS, draft_root=self.drafts, run_root=self.runs)

    def test_due_draft_is_queued_once_per_slot_with_its_start_values(self):
        saved = drafts.save_draft(flow(ON), root=self.drafts)
        outcome = self.tick()[saved["id"]]
        self.assertEqual(outcome["outcome"], "queued")
        run = runs.get_run(outcome["run_id"], self.runs)
        self.assertEqual((run["origin"], run["mode"], run["input"], run["status"]), ("schedule", "dry_run", {"topic": "server"}, "queued"))
        self.assertEqual(self.tick(MONDAY_0803.replace(minute=5)), {}, "same slot never starts twice")
        self.assertEqual(len(runs.list_runs(saved["id"], self.runs)), 1)

    def test_rejected_start_is_recorded_once_and_not_retried(self):
        broken = flow({**ON, "input": {}})  # {{input.topic}} has no value
        saved = drafts.save_draft(broken, root=self.drafts)
        outcome = self.tick()[saved["id"]]
        self.assertEqual(outcome["outcome"], "rejected")
        self.assertIn("topic", outcome["error"])
        self.assertEqual(self.tick(MONDAY_0803.replace(minute=6)), {})
        self.assertEqual(schedule.read_state(self.runs)[saved["id"]]["outcome"], "rejected")

    def test_active_run_of_the_same_draft_skips_the_slot(self):
        saved = drafts.save_draft(flow(ON), root=self.drafts)
        runs.create_run(saved["id"], 1, "dry_run", {"topic": "x"}, BINDINGS, root=self.runs, draft_root=self.drafts)
        self.assertEqual(self.tick()[saved["id"]]["outcome"], "skipped")

    def test_overview_lists_only_enabled_schedules(self):
        drafts.save_draft(flow({}), root=self.drafts)
        saved = drafts.save_draft(flow(ON), root=self.drafts)
        rows = schedule.overview(datetime(2026, 11, 23, 9, 0, tzinfo=ROME), self.drafts, self.runs)
        self.assertEqual([r["draft_id"] for r in rows], [saved["id"]])
        self.assertTrue(rows[0]["next_start"].startswith("2026-11-24T08:00"))

    def test_manual_runs_keep_manual_origin(self):
        saved = drafts.save_draft(flow(ON), root=self.drafts)
        run = runs.create_run(saved["id"], 1, "dry_run", {"topic": "x"}, BINDINGS, root=self.runs, draft_root=self.drafts)
        self.assertEqual(runs.summary(run)["origin"], "manual")
        with self.assertRaises(ValueError):
            runs.create_run(saved["id"], 1, "dry_run", {"topic": "x"}, BINDINGS, root=self.runs, draft_root=self.drafts, origin="cron")


if __name__ == "__main__":
    unittest.main()
