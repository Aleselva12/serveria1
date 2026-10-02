import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda
from core import execution_traces as traces
from core.architecture_api import router, architecture_graph


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(traces, 'TRACE_FILE', Path(self.temp.name) / 'traces.jsonl')
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_nested_callbacks_are_correlated_and_persisted(self):
        child = RunnableLambda(lambda x: x + 1).with_config(run_name='child_agent')
        parent = RunnableLambda(lambda x: child.invoke(x)).with_config(run_name='supervisor')
        trace = traces.ExecutionTrace('conversation', 'v1')
        trace.event('run', 'running')
        self.assertEqual(parent.invoke(1, config={'callbacks': [trace]}), 2)
        trace.event('run', 'completed')
        runs = traces.read_runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]['status'], 'completed')
        events = runs[0]['events']
        child_event = next(e for e in events if e['name'] == 'child_agent')
        parent_event = next(e for e in events if e['name'] == 'supervisor')
        self.assertEqual(child_event['parent_id'], parent_event['span_id'])
        self.assertTrue(all(e['run_id'] == trace.id for e in events))
        self.assertNotIn('inputs', events[1])

    def test_errors_and_unknown_ids(self):
        trace = traces.ExecutionTrace('thread', 'v1')
        span = uuid.uuid4()
        trace.on_tool_start({'name': 'test_tool'}, 'secret', run_id=span)
        trace.on_tool_error(ValueError('secret'), run_id=span)
        trace.event('run', 'error')
        app = FastAPI(); app.include_router(router)
        client = TestClient(app)
        response = client.get('/api/v1/runs/' + trace.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'error')
        self.assertNotIn('secret', response.text)
        self.assertEqual(client.get('/api/v1/runs/missing').status_code, 404)
        self.assertEqual(client.get('/api/v1/runs?limit=0').status_code, 422)

    def test_real_compiled_graph_and_stable_version(self):
        first = architecture_graph()
        self.assertEqual(first['errors'], [])
        self.assertEqual(first['version'], architecture_graph()['version'])
        self.assertEqual(len(first['graphs']), 5)
        from graph import graph
        supervisor = next(g for g in first['graphs'] if g['id'] == 'supervisor')
        self.assertEqual({(e['source'], e['target']) for e in supervisor['edges']},
                         {(str(e.source), str(e.target)) for e in graph.get_graph().edges})

    def test_running_and_newest_limit(self):
        for i in range(4):
            trace = traces.ExecutionTrace(str(i), 'v1')
            trace.event('run', 'running')
        result = traces.read_runs(2)
        self.assertEqual([r['thread_id'] for r in result], ['3', '2'])
        self.assertTrue(result[0]['note'])
