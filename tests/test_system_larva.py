import unittest

from core.system_larva import evaluate


class SystemLarvaTests(unittest.TestCase):
    def test_nominal_snapshot_takes_no_action(self):
        result = evaluate({
            "ownership_validation": {"valid": True},
            "permissions": {"validation": {"valid": True}},
            "runtime": {"accepting_runs": True},
            "diagnostics": {"write_error": None, "diagnostics": {"dropped": 0, "write_failures": 0, "worker_alive": True}},
        })
        self.assertEqual(result["status"], "nominal")
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["actions_taken"], [])
        self.assertFalse(result["may_execute_actions"])

    def test_objective_failures_are_classified_without_actions(self):
        result = evaluate({
            "ownership_validation": {"valid": False},
            "permissions": {"validation": {"valid": True}},
            "runtime": {"accepting_runs": False},
            "diagnostics": {"write_error": "OSError", "diagnostics": {"dropped": 2, "write_failures": 1, "worker_alive": False}},
        })
        self.assertEqual(result["status"], "critical")
        codes = {row["code"] for row in result["issues"]}
        self.assertIn("state_ownership_invalid", codes)
        self.assertIn("runtime_not_accepting", codes)
        self.assertIn("diagnostic_events_dropped", codes)
        self.assertEqual(result["actions_taken"], [])


if __name__ == "__main__":
    unittest.main()
