import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.domain import automation_drafts, automation_runs, automation_schedule


class AutomationReminderTests(unittest.TestCase):
    def test_midnight_run_schedules_same_day_reminder_once(self):
        self.check_midnight_run("live")

    def test_dry_run_does_not_save_notification(self):
        self.check_midnight_run("dry_run")

    def check_midnight_run(self, mode):
        midnight = datetime(2026, 11, 25, tzinfo=ZoneInfo("Europe/Rome"))
        with tempfile.TemporaryDirectory() as temp, \
             patch("core.domain.automation_engine.datetime", wraps=datetime) as clock, \
             patch("core.domain.automation_reminders.schedule", return_value="notification") as save:
            clock.now.side_effect = lambda zone: midnight.astimezone(zone)
            drafts, runs = Path(temp) / "drafts", Path(temp) / "runs"
            draft = automation_drafts.save_draft({
                "title": "Sveglia di prova",
                "nodes": [
                    {"id": "start", "kind": "trigger", "label": "Mezzanotte", "x": 0, "y": 0,
                     "config": {"schedule": {"enabled": True, "time": "00:00", "mode": mode}}},
                    {"id": "alarm", "kind": "reminder", "label": "Sveglia", "x": 220, "y": 0,
                     "config": {"time": "07:30"}},
                    {"id": "end", "kind": "output", "label": "Risultato", "x": 440, "y": 0},
                ],
                "edges": [
                    {"id": "a", "source": "start", "target": "alarm"},
                    {"id": "b", "source": "alarm", "target": "end"},
                ],
            }, root=drafts)
            options = {"bindings": {}, "draft_root": drafts, "run_root": runs}
            started = automation_schedule.tick(midnight, **options)[draft["id"]]
            result = automation_runs.process(automation_runs.get_run(started["run_id"], runs), runs)
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(result["nodes"]["alarm"]["result"]["deliver_at"], "2026-11-25T07:30:00+01:00")
            self.assertEqual(automation_schedule.tick(midnight, **options), {})
            if mode == "live":
                save.assert_called_once()
            else:
                save.assert_not_called()
