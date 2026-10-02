import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("tool_inventory", Path(__file__).resolve().parents[1] / "core/tool_inventory.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InventoryTest(unittest.TestCase):
    def test_current_agent_bindings_and_registered_routes(self):
        routes = [SimpleNamespace(path="/api/v1/server/files/upload", methods={"POST"}, name="upload", summary=None)]
        result = module.inventory(routes)
        self.assertEqual(result["errors"], [])
        tools = [e for e in result["entries"] if e["kind"] == "tool"]
        baseline = [e for e in tools if e["source"] in {s[0] for s in module.SOURCES} and not e["name"].startswith("calendar_")]
        self.assertGreaterEqual(len(baseline), 40)
        self.assertTrue(all(e["status"] == "connected" and e["agents"] for e in baseline))
        upload = next(e for e in result["entries"] if e["kind"] == "api")
        self.assertEqual(upload["status"], "unconnected")
        self.assertEqual(upload["group"], "File server")
        self.assertEqual(upload["agents"], [])

    def test_missing_source_is_reported_not_marked_implemented(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = module.inventory(root=Path(tmp))
        self.assertEqual(len(result["errors"]), 5)
        self.assertTrue(all(e["status"] == "planned" for e in result["entries"]))

    def test_calendar_moves_from_planned_to_connected_only_with_graph_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "calendar_tools.py").write_text('@tool\ndef calendar_create_event(title: str):\n    """Create an event proposal."""\n    pass\n\nCALENDAR_TOOLS = [calendar_create_event]\n')
            (root / "tools.py").write_text('from calendar_tools import CALENDAR_TOOLS\nsupervisor_tools = [*CALENDAR_TOOLS]\n')
            (root / "graph.py").write_text('model.bind_tools(supervisor_tools)\n')
            result = module.inventory(root=root)
            events = [e for e in result["entries"] if e["name"] == "calendar_create_event"]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["status"], "connected")
            (root / "graph.py").write_text('pass\n')
            events = [e for e in module.inventory(root=root)["entries"] if e["name"] == "calendar_create_event"]
            self.assertEqual(events[0]["status"], "unconnected")


if __name__ == "__main__":
    unittest.main()
