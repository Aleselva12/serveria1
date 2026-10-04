"""Requires a disposable pgvector database, never use the owner's real database."""
import json
import os
import unittest
from unittest.mock import patch
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from core.database import db_connection
from core.auth import provision
from core.governance import agent_tool, resolve
from core.permissions import require_permission, set_policy
from core.runtime import Runtime

@unittest.skipUnless(os.getenv('CORA_RUNTIME_TEST_DATABASE_URL'), 'Requires disposable PostgreSQL+pgvector')
class RuntimePostgresTests(unittest.TestCase):
    def setUp(self):
        import api
        self.runtime = Runtime()
        self.patch = patch.object(api,'runtime',self.runtime);self.patch.start()
        with db_connection() as c:
            c.execute('TRUNCATE app_sessions,app_users,action_approvals,tool_policies CASCADE')
        import core.permissions as permissions
        permissions._policy_time=0
        provision('Ale','a-long-local-password')
        self.client = TestClient(api.app,headers={'X-Cora-Client':'ui'})
        self.assertEqual(self.client.post('/auth/login',json={'username':'Ale','password':'a-long-local-password'}).status_code,200)
    def tearDown(self):
        self.client.close();self.runtime.shutdown();self.patch.stop()
        from core.database import close_pool
        close_pool()

    def test_login_logout_revocation_and_password_not_in_session(self):
        self.assertTrue(self.client.get('/auth/status').json()['authenticated'])
        with db_connection() as c:
            row=c.execute('SELECT * FROM app_sessions').fetchone()
        self.assertEqual(len(row['token_hash']),64)
        self.assertNotEqual(row['token_hash'],self.client.cookies.get('cora_session'))
        self.assertEqual(self.client.post('/auth/logout?all_sessions=true').status_code,200)
        self.assertEqual(self.client.get('/conversations').status_code,401)

    def test_expired_session_cannot_read_memory(self):
        with db_connection() as c: c.execute("UPDATE app_sessions SET expires_at=NOW()-INTERVAL '1 second'")
        self.assertEqual(self.client.get('/memory').status_code,401)

    def test_approval_applies_exact_action_once_and_rechecks_policy(self):
        effects=[]
        @agent_tool('supervisor', actions=('remember_memory',), effect="write", retry="never")
        def write_approval_test(value:str):
            """Write a test effect behind the actual permission engine."""
            require_permission('supervisor','remember_memory');effects.append(value);return {'saved':value}
        set_policy('supervisor','remember_memory','confirm')
        proposal=json.loads(write_approval_test.invoke({'value':'specific'}))
        self.assertEqual(effects,[])
        result=resolve(proposal['approval_id'],True,'Ale')
        self.assertEqual(result['status'],'approved');self.assertEqual(effects,['specific'])
        with self.assertRaises(ValueError):resolve(proposal['approval_id'],True,'Ale')
        second=json.loads(write_approval_test.invoke({'value':'second'}))
        set_policy('supervisor','remember_memory','blocked')
        with self.assertRaises(RuntimeError):resolve(second['approval_id'],True,'Ale')
        self.assertEqual(effects,['specific'])
        with db_connection() as c:
            row=c.execute('SELECT status FROM action_approvals WHERE id=%s',(second['approval_id'],)).fetchone()
        self.assertEqual(row['status'],'failed')

    def test_multi_permission_tool_has_one_exact_bundle_confirmation(self):
        effects=[]
        @agent_tool('structure_agent', actions=('create_plan', 'save_plan'), effect="write", retry="never")
        def write_multi_test(value:str):
            """A composite capability requires both permissions before its effect."""
            require_permission('structure_agent','create_plan')
            require_permission('structure_agent','save_plan')
            effects.append(value)
            return 'ok'
        set_policy('structure_agent','create_plan','confirm')
        set_policy('structure_agent','save_plan','confirm')
        proposal=json.loads(write_multi_test.invoke({'value':'one'}))
        with db_connection() as c: row=c.execute('SELECT actions FROM action_approvals WHERE id=%s',(proposal['approval_id'],)).fetchone()
        self.assertEqual(set(row['actions']),{'create_plan','save_plan'})
        self.assertEqual(effects,[])
        self.assertEqual(resolve(proposal['approval_id'],True,'Ale')['status'],'approved')
        self.assertEqual(effects,['one'])

    def test_contract_pinning_defaults_and_legacy_proposals(self):
        effects = []
        @agent_tool('supervisor', actions=('remember_memory',), effect='write', retry='never')
        def pinned_approval_test(value: str = 'default') -> str:
            """Pin the confirmed contract and normalized input before effects."""
            effects.append(value)
            return 'ok'
        set_policy('supervisor','remember_memory','confirm')
        proposal = json.loads(pinned_approval_test.invoke({}))
        with db_connection() as c:
            row = c.execute('SELECT * FROM action_approvals WHERE id=%s',(proposal['approval_id'],)).fetchone()
        self.assertEqual(row['payload'], {'value':'default'})
        self.assertEqual(row['capability_id'], 'supervisor.pinned_approval_test')
        self.assertEqual(row['contract_version'], 1)
        self.assertEqual(len(row['contract_digest']), 64)
        self.assertEqual(resolve(proposal['approval_id'],True,'Ale')['status'], 'approved')
        self.assertEqual(effects, ['default'])
        for assignment in ["contract_digest='changed'", "contract_version=2", "capability_id=NULL,contract_version=NULL,contract_digest=NULL"]:
            with self.subTest(assignment=assignment):
                id = json.loads(pinned_approval_test.invoke({}))['approval_id']
                with db_connection() as c:
                    c.execute('UPDATE action_approvals SET '+assignment+' WHERE id=%s',(id,))
                with self.assertRaises(RuntimeError): resolve(id,True,'Ale')
                self.assertEqual(effects, ['default'])
        id = json.loads(pinned_approval_test.invoke({}))['approval_id']
        with db_connection() as c:
            c.execute('UPDATE action_approvals SET contract_version=NULL WHERE id=%s',(id,))
        self.assertEqual(resolve(id,False,'Ale')['status'], 'rejected')

    def test_expired_approval_and_rejection_never_execute(self):
        effects=[]
        @agent_tool('supervisor', actions=('remember_memory',), effect="write", retry="never")
        def write_expiry_test(value:str):
            """Test expiry before an authorized effect."""
            require_permission('supervisor','remember_memory');effects.append(value);return 'ok'
        set_policy('supervisor','remember_memory','confirm')
        a=json.loads(write_expiry_test.invoke({'value':'expired'}))['approval_id']
        with db_connection() as c:c.execute("UPDATE action_approvals SET expires_at=NOW()-INTERVAL '1 second' WHERE id=%s",(a,))
        with self.assertRaises(ValueError):resolve(a,True,'Ale')
        b=json.loads(write_expiry_test.invoke({'value':'rejected'}))['approval_id']
        self.assertEqual(resolve(b,False,'Ale')['status'],'rejected');self.assertEqual(effects,[])

    def test_chat_stream_persists_and_returns_the_canonical_result(self):
        import api
        from langchain_core.messages import AIMessage
        class FakeGraph:
            def stream(self,*args,**kwargs):
                yield 'messages',(AIMessage(content='Ciao'),{'langgraph_node':'agent','langgraph_step':1})
                yield 'values',{'messages':[AIMessage(content='Ciao') ]}
        cid=str(uuid4())
        with patch.object(api,'graph',FakeGraph()):
            created=self.client.post('/api/v1/chat/runs',json={'message':'hello','thread_id':cid})
            self.assertEqual(created.status_code,202)
            run=self.runtime.get(created.json()['id']);self.assertTrue(run.done.wait(5))
        self.assertEqual(run.status,'completed');self.assertEqual(run.result['response'],'Ciao')
        # Runtime endpoints share the same global instance in real production.
        with patch('core.runtime_api.runtime',self.runtime):
            streamed=self.client.get('/api/v1/runtime/runs/'+run.id+'/events')
        self.assertIn('event: resync',streamed.text);self.assertIn('event: result',streamed.text)
        rows=self.client.get('/conversations/'+cid+'/messages').json()
        self.assertEqual([r['content'] for r in rows],['hello','Ciao'])
        with db_connection() as c:
            rows=c.execute('SELECT embedding,embedding_model FROM messages WHERE conversation_id=%s',(cid,)).fetchall()
        self.assertTrue(all(r['embedding'] is None and r['embedding_model'] is None for r in rows))

    def test_summary_cache_covers_old_history_and_is_not_semantic_memory(self):
        from core.context_budget import prepare_context
        from langchain_core.messages import AIMessage
        cid=uuid4()
        with db_connection() as c:
            c.execute('INSERT INTO conversations (id) VALUES (%s)',(cid,))
            for i in range(12):
                c.execute('INSERT INTO messages (id,conversation_id,role,content,created_at) VALUES (%s,%s,%s,%s,%s)',(uuid4(),cid,'user',str(i)+'x'*4000,datetime.now(timezone.utc)+timedelta(seconds=i)))
            count=c.execute('SELECT count(*) AS n FROM memories').fetchone()['n']
        class Summarizer:
            def invoke(self,*args,**kwargs):return AIMessage(content='Derived summary')
        with patch('core.models.get_chat_model',return_value=Summarizer()) as model:
            context=prepare_context(str(cid));self.assertEqual(context[0]['name'],'conversation_summary');self.assertEqual(context[-1]['content'],'11'+'x'*4000)
            self.assertTrue(model.called)
        with patch('core.models.get_chat_model') as model:
            repeated=prepare_context(str(cid));self.assertEqual(repeated,context);model.assert_not_called()
        with db_connection() as c:self.assertEqual(c.execute('SELECT count(*) AS n FROM memories').fetchone()['n'],count)

    def test_transaction_rolls_back_and_connection_is_reused(self):
        try:
            with db_connection() as c:
                c.execute("INSERT INTO tool_policies (actor,action,policy) VALUES ('test','test','auto')")
                raise ValueError('rollback')
        except ValueError:pass
        with db_connection() as c:
            self.assertIsNone(c.execute("SELECT * FROM tool_policies WHERE actor='test'").fetchone())

    def test_tool_reported_error_is_not_approved_success(self):
        @agent_tool('supervisor', actions=('remember_memory',), effect="write", retry="never")
        def test_report_error(value:str):
            """A tool may return a structured error instead of raising."""
            require_permission('supervisor','remember_memory');return json.dumps({'status':'error','error':'failed'})
        set_policy('supervisor','remember_memory','confirm')
        a=json.loads(test_report_error.invoke({'value':'test'}))['approval_id']
        with self.assertRaises(RuntimeError):resolve(a,True,'Ale')
        with db_connection() as c:row=c.execute('SELECT status,result FROM action_approvals WHERE id=%s',(a,)).fetchone()
        self.assertEqual(row['status'],'uncertain');self.assertIn('error',row['result'])

    def test_empty_memory_skips_embedding_and_unrelated_memory_is_filtered(self):
        from core.memory import search_memories
        with db_connection() as c: c.execute('TRUNCATE memories CASCADE')
        with patch('core.memory.embed_text') as embed:
            self.assertEqual(search_memories('test'),[]);embed.assert_not_called()
        with db_connection() as c:
            c.execute("INSERT INTO memories (id,memory_type,key,content,source) VALUES (%s,'fact','calendar','Meeting Monday','test')",(uuid4(),))
        with patch('core.memory.embed_text',return_value=(None,None)):
            self.assertEqual(search_memories('unrelated phrase'),[])
            self.assertEqual(len(search_memories('Meeting')),1)

    def test_background_summary_yields_and_resumes_from_persisted_boundary(self):
        from core.context_budget import prepare_context,ContextDeferred
        from langchain_core.messages import AIMessage
        cid=uuid4()
        with db_connection() as c:
            c.execute('INSERT INTO conversations (id) VALUES (%s)',(cid,))
            for i in range(12):
                c.execute('INSERT INTO messages (id,conversation_id,role,content,created_at) VALUES (%s,%s,%s,%s,%s)',(uuid4(),cid,'user',str(i)+'x'*4000,datetime.now(timezone.utc)+timedelta(seconds=i)))
        seen=[]
        class Model:
            def invoke(self,messages,**kwargs):
                seen.extend(m['content'] for m in json.loads(messages[1].content)['messages'])
                return AIMessage(content='summary')
        with patch('core.models.get_chat_model',return_value=Model()):
            with self.assertRaises(ContextDeferred): prepare_context(str(cid),should_yield=lambda:bool(seen))
            covered=len(seen)
            self.assertGreater(covered,0)
            with db_connection() as c:
                self.assertIsNotNone(c.execute('SELECT * FROM conversation_summaries WHERE conversation_id=%s',(cid,)).fetchone())
            context=prepare_context(str(cid))
        self.assertEqual(len(seen),len(set(seen)))
        self.assertEqual(context[-1]['content'],'11'+'x'*4000)

    def test_specialist_stream_resets_same_step_and_returns_canonical_answer(self):
        import api
        from langchain_core.messages import AIMessage
        class Graph:
            def stream(self,*args,**kwargs):
                yield 'messages',(AIMessage(content='Delegate',id='supervisor'),{'langgraph_node':'agent','langgraph_step':1,'cora_role':'supervisor'})
                yield 'messages',(AIMessage(content='Specialist',id='research'),{'langgraph_node':'agent','langgraph_step':1,'cora_role':'research'})
                yield 'values',{'messages':[AIMessage(content='Canonical result')]}
        with patch.object(api,'graph',Graph()):
            created=self.client.post('/api/v1/chat/runs',json={'message':'query','thread_id':str(uuid4())})
            run=self.runtime.get(created.json()['id']);self.assertTrue(run.done.wait(5))
        self.assertEqual(run.status,'completed');self.assertEqual(run.output,'Specialist')
        self.assertEqual(run.result['response'],'Canonical result');self.assertIn('first_token_ms',run.timings)

    def test_real_graph_delegation_streams_specialist_tokens_and_persists_child(self):
        import graph as supervisor
        import search_agent.search_graph as specialist
        from langchain_core.language_models.fake_chat_models import FakeListChatModel,FakeMessagesListChatModel
        from langchain_core.messages import AIMessage
        from core.event_bus import bus
        root=FakeMessagesListChatModel(responses=[AIMessage(content='',tool_calls=[{'name':'search_agent_tool','args':{'query':'read'},'id':'delegation','type':'tool_call'}])]).with_config(metadata={'cora_role':'supervisor'})
        child=FakeListChatModel(responses=['Risposta progressiva']).with_config(metadata={'cora_role':'research'})
        with patch.object(supervisor,'model_with_tools',root),patch.object(specialist,'model_with_tools',child),patch.object(supervisor,'search_memories',return_value=[]):
            response=self.client.post('/api/v1/chat/runs',json={'message':'read docs','thread_id':str(uuid4())})
            run=self.runtime.get(response.json()['id']);self.assertTrue(run.done.wait(5))
        self.assertEqual(run.status,'completed',run.error_type)
        self.assertEqual(run.result['response'],'Risposta progressiva')
        events,_=bus.read(0,run.id)
        deltas=[e for e in events if e['type']=='chat.delta' and e['source']=='research']
        self.assertGreater(len(deltas),1,[(e["type"],e["source"],e["payload"]) for e in events])
        self.assertEqual(''.join(e['payload']['text'] for e in deltas),'Risposta progressiva')
        with db_connection() as c:
            child=c.execute('SELECT * FROM runtime_runs WHERE parent_run_id=%s',(run.id,)).fetchone()
        self.assertEqual(child['status'],'completed')
