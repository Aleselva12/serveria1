import unittest
from unittest.mock import patch

from core.governance import agent_tool, executables
from core.operational_capabilities import operational_registry
from core.component_bus import component_bus


class OperationalCapabilitiesTests(unittest.TestCase):
    def setUp(self):
        self.keys = set(executables)

    def tearDown(self):
        for key in set(executables) - self.keys:
            executables.pop(key)

    def test_registry_is_compact_operational_view(self):
        @agent_tool("supervisor", capability="registry_probe", actions=("calculate",), effect="compute", retry="safe")
        def probe(value: int) -> str:
            """Registry probe."""
            return str(value)

        with patch("core.operational_capabilities.load_capabilities"),              patch("core.runtime_status.component_runtime_status", return_value={"components":{"supervisor":{"status":"ready","checks":{}}}}),              patch("core.models.resolve_model", return_value={"model":"small","machine_id":"local","role":"supervisor","source":"test","configuration_id":"x"}):
            registry = operational_registry()
        row = next(item for item in registry["capabilities"] if item["id"] == "supervisor.registry_probe")
        self.assertEqual(row["required_inputs"], ["value"])
        self.assertEqual(row["effect"], "compute")
        self.assertEqual(row["retry"], "safe")
        self.assertEqual(row["runtime"]["status"], "ready")
        self.assertIn("permissions", row)

    def test_agent_tool_uses_component_bus_and_returns_native_output(self):
        @agent_tool("supervisor", capability="bus_probe", actions=("calculate",), effect="compute", retry="safe")
        def probe(value: int) -> str:
            """Bus probe."""
            return str(value + 1)

        with patch("core.operation_journal.begin", return_value=None),              patch("core.operation_journal.finish", return_value=None),              patch.object(component_bus, "dispatch", wraps=component_bus.dispatch) as dispatch:
            self.assertEqual(probe.invoke({"value": 2}), "3")
        self.assertTrue(dispatch.called)
        state = component_bus.snapshot()["supervisor"]
        self.assertEqual(state["last_decision"], "complete")


if __name__ == "__main__":
    unittest.main()
