import unittest
from unittest.mock import patch

from core.error_decisions import decide


class ErrorDecisionTests(unittest.TestCase):
    def test_standard_decisions(self):
        self.assertEqual(decide(status="ok"), "complete")
        self.assertEqual(decide(status="pending"), "needs_approval")
        self.assertEqual(decide(status="uncertain", effect="write"), "effect_uncertain")
        self.assertEqual(decide(status="failed", error_code="TimeoutError"), "resource_unavailable")
        self.assertEqual(decide(status="failed", error_code="ValidationError", effect="compute", retry="safe"), "retry_safe")
        self.assertEqual(decide(status="failed", error_code="ValidationError", effect="write", retry="never"), "needs_replan")
        self.assertEqual(decide(status="failed", error_code="RunStopped"), "cancelled")


if __name__ == "__main__":
    unittest.main()
