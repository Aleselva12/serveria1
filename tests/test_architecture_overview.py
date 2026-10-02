import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.architecture_api import architecture_overview, router


class OverviewTests(unittest.TestCase):
    def test_overview_has_separate_agents_and_actual_bound_delegations(self):
        from tools import supervisor_tools
        with patch('core.architecture_api.architecture_graph', side_effect=AssertionError('No internal graph inspection')):
            overview = architecture_overview()
        self.assertEqual({n['id'] for n in overview['nodes'] if n['kind'] == 'agent'},
                         {'supervisor', 'structure_agent', 'local_research_agent', 'audio_agent', 'email_quotes_agent'})
        self.assertNotIn('graphs', overview)
        self.assertNotIn('tools', {n['id'] for n in overview['nodes']})
        self.assertTrue(all(c['kind'] == 'core' for c in overview['components']))
        self.assertEqual(len([e for e in overview['edges'] if e['kind'] == 'delegation']), 4)
        with patch('tools.supervisor_tools', [t for t in supervisor_tools if t.name != 'audio_agent_tool']):
            changed = architecture_overview()
        self.assertNotIn('audio_agent', {e['target'] for e in changed['edges']})
        self.assertIn('audio_agent', {n['id'] for n in changed['nodes']})
        self.assertNotEqual(overview['version'], changed['version'])

    def test_direct_paths_are_registered_routes_and_no_agent_tools(self):
        from core.calendar_api import router as calendar_router
        overview = architecture_overview()
        calendar = next(p for p in overview['direct_paths'] if p['id'] == 'calendar_direct')
        self.assertEqual(set(calendar['routes']), {r.path for r in calendar_router.routes})
        self.assertNotIn('calculator_tool', {p['id'] for p in overview['direct_paths']})
        self.assertEqual(overview['automations'][0]['id'], 'chat_persistence')
        app = FastAPI(); app.include_router(router)
        result = TestClient(app).get('/api/v1/architecture/overview')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['framework'], 'LangGraph')
