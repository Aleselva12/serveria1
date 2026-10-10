import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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
        self.assertEqual(upload["status"], "direct")
        self.assertEqual(upload["group"], "File server")
        self.assertEqual(upload["agents"], [])

    def test_api_integration_intentions_and_existing_wrappers_are_separate(self):
        from core.tool_backlog import api_integration
        self.assertEqual(api_integration('/api/v1/server/files/children', 'GET', set())[0], 'integration_needed')
        self.assertEqual(api_integration('/api/v1/server/files/children', 'GET', {'server_list_files'})[0], 'direct')
        for path, method in (('/auth/login','POST'),('/api/v1/server/files/upload','POST'),('/api/v1/calendar/events','GET'),('/tools/drafts','POST')):
            self.assertEqual(api_integration(path, method, set())[0], 'direct')
        self.assertEqual(api_integration('/api/v1/library/files/import','POST',set())[1], 'library_import_file')

    def test_attachment_support_is_not_still_planned_and_file_tools_have_reminders(self):
        result = module.inventory()
        planned = {e['name'] for e in result['entries'] if e['status'] == 'planned'}
        self.assertNotIn('Allegati della chat', planned)
        self.assertIn('server_read_file', planned)
        self.assertIn('library_import_file', planned)

    def test_executable_catalog_uses_registry_not_source_inference(self):
        from core.governance import capability_registry, find_capability
        registry = capability_registry()
        self.assertTrue(registry['validation']['valid'])
        with patch.object(module, '_parse', side_effect=AssertionError('No AST authority')):
            catalog = module.inventory()
        declared = {c['id']:c for e in catalog['entries'] for c in e.get('capabilities',[])}
        production = {c['id']:c for c in registry['tools'] if c['id'] in declared}
        self.assertGreaterEqual(len(production),60)
        self.assertEqual(declared,{k:{key:value for key,value in c.items() if key not in {'actions','revision'}} for k,c in production.items()})
        calendar = next(e for e in catalog['entries'] if e['name']=='calendar_create_event')
        self.assertEqual(len(calendar['capabilities']),4)
        for c in calendar['capabilities']:
            self.assertTrue(c['connected'])
            _, executable = find_capability(c['id'])
            self.assertEqual(c['input_schema'], executable['input_model'].model_json_schema())
            self.assertNotIn('actor',c['input_schema']['properties'])
            self.assertNotIn('user_approved',c['input_schema']['properties'])

    def test_missing_source_is_reported_not_marked_implemented(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = module.inventory(root=Path(tmp))
        self.assertEqual(len(result["errors"]), 6)
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
