import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from core.domain import mail, mail_summary_jobs as jobs


class MailSummaryJobsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = patch.object(mail, "directory", return_value=Path(self.tmp.name))
        self.dir.start()
        jobs._PENDING = None
        self.assertTrue(jobs._acquire_runner_lock())

    def tearDown(self):
        jobs._PENDING = None
        jobs._release_runner_lock()
        self.dir.stop()
        self.tmp.cleanup()

    def test_enqueue_is_not_duplicated_and_job_result_is_stored(self):
        self.assertTrue(jobs.enqueue("all", "yesterday")["accepted"])
        self.assertEqual(jobs.enqueue("a", "inbox")["reason"], "queued")
        job = jobs._take_pending()
        with patch.object(mail, "summarize", return_value={"status": "ready", "summary": "Fatto", "messages": [{}], "errors": {}}), \
                patch.object(jobs, "_notify") as notify:
            jobs.run_job(job)
        stored = jobs.latest()["job"]
        self.assertEqual((stored["status"], stored["summary"], stored["trigger"]), ("ready", "Fatto", "manual"))
        self.assertIsNotNone(stored["finished_at"])
        notify.assert_called_once()

    def test_failure_keeps_only_error_class(self):
        with patch.object(mail, "summarize", side_effect=RuntimeError("secret token xyz")):
            record = jobs.run_job({"selection": "all", "scope": "inbox", "trigger": "manual"})
        self.assertEqual(record["status"], "failed")
        self.assertNotIn("secret", record["notice"])

    def test_invalid_account_rejected(self):
        with self.assertRaises(ValueError):
            jobs.enqueue("z", "inbox")

    def test_nightly_due_once_per_day_after_time(self):
        with patch.dict("os.environ", {"CORA_MAIL_SUMMARY_TIME": "03:00"}):
            self.assertFalse(jobs._nightly_due(datetime(2026, 11, 16, 2, 59, tzinfo=mail.ROME)))
            self.assertTrue(jobs._nightly_due(datetime(2026, 11, 16, 3, 0, tzinfo=mail.ROME)))
            jobs._write(jobs._nightly_path(), {"day": "2026-11-16"})
            self.assertFalse(jobs._nightly_due(datetime(2026, 11, 16, 9, 0, tzinfo=mail.ROME)))
            self.assertTrue(jobs._nightly_due(datetime(2026, 11, 17, 3, 5, tzinfo=mail.ROME)))

    def test_nightly_not_started_by_daytime_restart(self):
        with patch.dict("os.environ", {"CORA_MAIL_SUMMARY_TIME": "03:00", "CORA_MAIL_SUMMARY_WINDOW_HOURS": "4"}):
            self.assertTrue(jobs._nightly_due(datetime(2026, 11, 16, 6, 59, tzinfo=mail.ROME)))
            self.assertFalse(jobs._nightly_due(datetime(2026, 11, 16, 7, 0, tzinfo=mail.ROME)))
            self.assertFalse(jobs._nightly_due(datetime(2026, 11, 16, 22, 46, tzinfo=mail.ROME)))

    def test_second_process_cannot_run_or_recover_jobs(self):
        jobs._write(jobs._latest_path(), {"status": "running", "selection": "all", "scope": "yesterday"})
        held, jobs._RUNNER_LOCK = jobs._RUNNER_LOCK, None
        try:
            # Same lock file opened again behaves like the verification process in the container.
            self.assertFalse(jobs._acquire_runner_lock())
            jobs.start()
            self.assertIsNone(jobs._THREAD if jobs._THREAD and jobs._THREAD.is_alive() else None)
            self.assertEqual(jobs.latest()["job"]["status"], "running")
            with self.assertRaises(ValueError):
                jobs.enqueue("all", "inbox")
        finally:
            jobs._RUNNER_LOCK = held

    def test_interrupted_running_job_is_marked_failed(self):
        jobs._write(jobs._latest_path(), {"status": "running", "selection": "all", "scope": "inbox"})
        jobs._recover_interrupted()
        self.assertEqual(jobs.latest()["job"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
