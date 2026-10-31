import unittest
from unittest.mock import patch

from core import system_coordinator
from core.registry import get_component


class SystemCoordinatorTests(unittest.TestCase):
    def test_state_ownership_has_one_authority_per_concern(self):
        validation = system_coordinator.validate_ownership()
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["duplicate_concerns"], [])
        concerns = {row["concern"] for row in system_coordinator.ownership_manifest()}
        self.assertIn("task_lifecycle", concerns)
        self.assertIn("permissions", concerns)
        self.assertIn("context_selection", concerns)

    def test_registry_exposes_read_only_system_coordinator(self):
        component = get_component("system_coordinator")
        self.assertIsNotNone(component)
        self.assertEqual(component["kind"], "core")
        self.assertTrue(component["available"])

    def test_snapshot_is_explicitly_non_executing(self):
        fake_runtime = type("FakeRuntime", (), {"closed": False, "snapshot": lambda self: []})()
        fake_bus = type("FakeBus", (), {"process_id": "p", "sequence": 3, "events": type("E", (), {"maxlen": 512})()})()
        with patch("core.runtime.runtime", fake_runtime),              patch("core.event_bus.bus", fake_bus),              patch("core.database.pool_stats", return_value={"pool_size": 1}),              patch("core.execution_traces.trace_status", return_value={"write_error": None}),              patch("core.component_bus.component_bus.snapshot", return_value={}),              patch("core.permissions.permission_manifest", return_value=[]),              patch("core.permissions.validate_permission_configuration", return_value={"valid": True}):
            snapshot = system_coordinator.snapshot()
        self.assertEqual(snapshot["mode"], "read_only_coordinator")
        self.assertTrue(all(value is False for value in snapshot["guarantees"].values()))


if __name__ == "__main__":
    unittest.main()
