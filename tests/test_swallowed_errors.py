"""Best-effort failures leave a metadata-only trace, without flooding the log."""
import unittest
from unittest.mock import patch

from core.infra import logging as cora_logging


class SwallowedErrorTests(unittest.TestCase):
    def setUp(self):
        cora_logging._REPORTED.clear()
        self.addCleanup(cora_logging._REPORTED.clear)

    def test_reports_only_the_error_type_never_the_message(self):
        with patch.object(cora_logging, "log_event") as event, self.assertLogs("cora.runner", "WARNING") as logs:
            self.assertTrue(cora_logging.report_swallowed_error(
                "cycle", RuntimeError("cliente Rossi, password 123"), component="runner"))
        self.assertEqual(event.call_args.kwargs["data"], {"error_type": "RuntimeError"})
        self.assertEqual(event.call_args.kwargs["status"], "error")
        self.assertNotIn("Rossi", "\n".join(logs.output))

    def test_a_repeating_failure_is_reported_again_only_after_the_quiet_period(self):
        with patch.object(cora_logging, "log_event") as event, self.assertLogs("cora.runner", "WARNING"), \
                patch.object(cora_logging.time, "monotonic", side_effect=[0, 10, 20, 700]):
            results = [cora_logging.report_swallowed_error("cycle", error, component="runner")
                       for error in (OSError(), OSError(), ValueError(), ValueError())]
        # Same type within the quiet period is skipped; a new type or the expiry reports again.
        self.assertEqual(results, [True, False, True, True])
        self.assertEqual(event.call_count, 3)

    def test_a_broken_event_bus_never_escapes_to_the_caller(self):
        with patch.object(cora_logging, "log_event", side_effect=RuntimeError("bus down")), \
                self.assertLogs("cora.runner", "WARNING"):
            self.assertTrue(cora_logging.report_swallowed_error("cycle", OSError(), component="runner"))


if __name__ == "__main__":
    unittest.main()
