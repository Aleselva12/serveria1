"""Reproducible offline A/B: python -m tests.programmer_context_benchmark is not required.
Run from repository root: python tests/programmer_context_benchmark.py
Uses scripted model responses, real graph/workspace/check tools, mocked DB journal.
No cloud, live code changes, release jobs or external model calls.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from programmer_agent import programmer_graph as pg, workspace as ws


def run_case(active, broken=False):
    samples = []
    with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {'CORA_CONTEXT_MANAGER_ENABLED':str(active).lower(),
                                                   'CORA_PROGRAMMER_WORKSPACE_ROOT':folder + '/work'}))
        source = Path(folder) / 'source'
        source.mkdir()
        (source / 'sample.py').write_text('value = 1\n')
        identifier = ws.create('Offline A/B', source)['id']
        stack.enter_context(ws.bind_workspace(identifier))
        class ScriptedModel:
            def bind_tools(self, tools):
                self.names = {t.name for t in tools}
                return self
            def invoke(self, messages):
                results = [m for m in messages if isinstance(m, ToolMessage)]
                if len(results) == 0:
                    name, args = 'programmer_read_file', {'path':'sample.py'}
                elif len(results) == 1:
                    read = json.loads(results[-1].content)
                    name, args = 'programmer_write_file', {'path':'sample.py', 'expected_sha256':read['sha256'],
                                                          'content':'invalid !!!' if broken else 'value = 2\n'}
                elif len(results) == 2:
                    name, args = 'programmer_check', {'profile':'syntax'}
                else:
                    check = json.loads(results[-1].content)
                    return AIMessage('Verifica fallita' if not check['passed'] else 'Sintassi verificata')
                assert name in self.names, name
                return AIMessage('', tool_calls=[{'name':name, 'args':{'workspace_id':identifier, **args},
                                                   'id':str(len(results)), 'type':'tool_call'}])
        stack.enter_context(patch.object(pg.request_router, 'classify', return_value={
            'status':'classified', 'route': {'intent':'modification',
            'context':['current','files'], 'tool_groups':['edit'],
            'difficulty':2, 'confidence':0.95}, 'duration_ms':0}))
        stack.enter_context(patch.object(pg, 'get_chat_model', return_value=ScriptedModel()))
        stack.enter_context(patch.object(pg, 'with_permanent_context', side_effect=lambda p:p))
        stack.enter_context(patch.object(pg, 'record_metric', side_effect=lambda kind, payload:samples.append({'kind':kind, **payload})))
        stack.enter_context(patch('core.operation_journal.begin', return_value='offline'))
        stack.enter_context(patch('core.operation_journal.finish'))
        stack.enter_context(patch('core.database.database_configured', return_value=True))
        stack.enter_context(patch('core.permissions.policy_overrides', return_value={}))
        started = time.perf_counter()
        result = pg.graph.invoke({'messages':[HumanMessage('Modifica sample.py e verifica la sintassi')]}, {'recursion_limit':20})
        elapsed = (time.perf_counter() - started)*1000
        assert (source / 'sample.py').read_text() == 'value = 1\n'
        evidence = next(s for s in samples if s['kind'] == 'verification')
        assert evidence['checks']['syntax']['passed'] is not broken
        return {'enabled':active, 'scenario':'invalid_syntax' if broken else 'valid_edit',
                'offline_graph_ms':round(elapsed, 2), 'real_ollama_tokens':None,
                'final_response':result['messages'][-1].content, 'metrics':samples}


def benchmark():
    return {'mode':'offline_scripted_model_not_ollama', 'cases':[run_case(active, broken) for broken in (False, True) for active in (False, True)]}


if __name__ == '__main__':
    print(json.dumps(benchmark(), ensure_ascii=False, indent=2))
