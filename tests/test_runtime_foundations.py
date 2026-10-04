import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from core.auth import AuthMiddleware, password_hash, verify_password
from core.context_budget import fit_messages
from core.event_bus import EventBus
from core.runtime import Runtime, Run, RunStopped, checkpoint, current_run
from core.governance import agent_tool, approved_action
from core.permissions import require_permission

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.file = patch('core.execution_traces.TRACE_FILE', Path(self.temp.name)/'traces.jsonl')
        self.file.start()
        self.journal = patch('core.operation_journal.begin',return_value=None);self.journal.start()
        self.finish = patch('core.operation_journal.finish',return_value=None);self.finish.start()
        self.runtime = Runtime(persistent=False)
    def tearDown(self):
        self.runtime.shutdown(); self.journal.stop(); self.finish.stop(); self.file.stop(); self.temp.cleanup()

    def test_serial_fifo_and_per_conversation_exclusion(self):
        release, started = threading.Event(), threading.Event()
        order = []
        def work(run):
            order.append(run.thread_id); started.set(); release.wait(2); return {}
        a = self.runtime.submit('one',work); self.assertTrue(started.wait(1))
        with self.assertRaises(ValueError): self.runtime.submit('one',work)
        b = self.runtime.submit('two', lambda run: order.append('two') or {})
        c = self.runtime.submit('three', lambda run: order.append('three') or {})
        self.assertEqual(b.status,'queued'); release.set()
        for r in [a,b,c]: self.assertTrue(r.done.wait(2))
        self.assertEqual(order,['one','two','three'])

    def test_cancel_keeps_slot_until_blocking_operation_returns(self):
        release, started = threading.Event(), threading.Event()
        def blocking(run): started.set(); release.wait(2); checkpoint(); return {}
        a=self.runtime.submit('one',blocking); self.assertTrue(started.wait(1)); a.stop()
        b=self.runtime.submit('two',lambda run:{})
        self.assertEqual(a.status,'cancelling'); self.assertFalse(a.done.is_set()); self.assertEqual(b.status,'queued')
        release.set(); self.assertTrue(a.done.wait(2)); self.assertTrue(b.done.wait(2))
        self.assertEqual(a.status,'cancelled'); self.assertEqual(b.status,'completed')

    def test_queued_cancel_never_executes_and_failure_releases_slot(self):
        release, started=threading.Event(),threading.Event()
        a=self.runtime.submit('one', lambda run: started.set() or release.wait(2) or {})
        self.assertTrue(started.wait(1)); called=[]
        b=self.runtime.submit('two',lambda run:called.append(True)); b.stop()
        self.assertTrue(b.done.wait(2)); self.assertEqual(b.status,'cancelled'); self.assertEqual(called,[])
        release.set(); self.assertTrue(a.done.wait(2))
        def fail(run): raise OSError('secret error text')
        c=self.runtime.submit('three',fail); self.assertTrue(c.done.wait(2)); self.assertEqual(c.status,'failed')
        self.assertEqual(c.error_type,'OSError')
        trace=(Path(self.temp.name)/'traces.jsonl').read_text(); self.assertNotIn('secret error text',trace)

    def test_timeout_and_invalid_transitions(self):
        run=Run('one',timeout=.01); run.created-=1
        with self.assertRaises(RunStopped): run.check()
        self.assertEqual(run.reason,'timed_out')
        run.transition('timed_out')
        with self.assertRaises(ValueError): run.transition('running')

    def test_bus_bounded_replay_and_isolation(self):
        bus=EventBus(2)
        for r in ['one','two','one']: bus.publish('test','tool',run_id=r)
        events,gap=bus.read(1,'one'); self.assertFalse(gap); self.assertEqual([e['sequence'] for e in events],[3])
        bus.publish('test','tool',run_id='two'); self.assertTrue(bus.read(1)[1]); self.assertEqual(len(bus.events),2)

    def test_budget_preserves_system_and_drops_orphan_tools(self):
        with patch.dict(os.environ,{'CORA_CONTEXT_TOKENS':'4096'}):
            messages=[SystemMessage('identity'),HumanMessage('x'*7000),AIMessage('',tool_calls=[{'id':'a','name':'tool','args':{}}]),ToolMessage('result',tool_call_id='a'),HumanMessage('recent')]
            fitted=fit_messages(messages,reserve=1024)
            self.assertEqual(fitted[0].content,'identity'); self.assertEqual(fitted[-1].content,'recent')
            self.assertFalse(isinstance(fitted[1],ToolMessage))
            with self.assertRaises(ValueError): fit_messages([HumanMessage('x'*20000)])

    def test_confirm_cannot_be_satisfied_by_a_different_payload(self):
        writes=[]
        @agent_tool('supervisor', actions=('remember_memory',), effect="write", retry="never")
        def write_test(content:str):
            """Test side effect guarded by exact approval binding."""
            require_permission('supervisor','remember_memory')
            writes.append(content)
            return 'ok'
        with patch('core.permissions.policy_overrides',return_value={('supervisor','remember_memory'):'confirm'}), patch('core.governance.propose',return_value={'id':'proposal'}) as propose:
            result=json.loads(write_test.invoke({'content':'first'})); self.assertEqual(result['status'],'pending'); self.assertEqual(writes,[])
            tool_id=propose.call_args.args[2]
            token=approved_action.set(('supervisor','remember_memory',tool_id,{'content':'first'}))
            try:
                self.assertEqual(write_test.invoke({'content':'first'}),'ok')
                self.assertEqual(json.loads(write_test.invoke({'content':'second'}))['status'],'pending')
            finally: approved_action.reset(token)
            self.assertEqual(writes,['first'])

class AuthTests(unittest.TestCase):
    def test_hash_salted_and_wrong_password_rejected(self):
        a=password_hash('long-personal-password'); b=password_hash('long-personal-password')
        self.assertNotEqual(a,b); self.assertTrue(verify_password('long-personal-password',a)); self.assertFalse(verify_password('other',a))

    def test_global_guard_does_not_accept_loopback_or_legacy_token(self):
        import api
        with patch('core.auth.session_user',return_value=None), TestClient(api.app) as client:
            for path in ['/health','/capabilities','/memory','/conversations','/api/v1/runtime','/api/v1/runtime/operations','/api/v1/runtime/runs','/docs','/openapi.json']:
                with self.subTest(path=path): self.assertEqual(client.get(path,headers={'Authorization':'Bearer old-token'}).status_code,401)
            self.assertEqual(client.post('/chat',json={'message':'test'},headers={'X-Cora-Client':'ui'}).status_code,401)

    def test_cookie_writes_require_browser_header_and_allowed_origin(self):
        app=FastAPI(); app.add_middleware(AuthMiddleware)
        @app.post('/write')
        def write(): return {'ok':True}
        with patch('core.auth.session_user',return_value={'id':'owner','username':'Ale'}), TestClient(app) as client:
            self.assertEqual(client.post('/write').status_code,403)
            self.assertEqual(client.post('/write',headers={'X-Cora-Client':'ui','Origin':'https://evil.example'}).status_code,403)
            self.assertEqual(client.post('/write',headers={'X-Cora-Client':'ui','Origin':'http://localhost:5173'}).status_code,200)
