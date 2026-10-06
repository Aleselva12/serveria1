"""Memory edits and context selection must not silently discard owner intent."""
import os
import json
import unittest
from uuid import uuid4
from unittest.mock import patch
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from core.context_budget import fit_messages, ContextOverflow, prepare_context, ContextDeferred
from core.database import db_connection
from core.memory import save_memory, search_memories, memory_history, MemoryConflict


class ContextContractTests(unittest.TestCase):
    def test_parallel_tool_exchange_is_atomic_and_current_user_is_retained(self):
        calls=[{'id':str(i),'name':'read','args':{'query':'q'}} for i in range(2)]
        turn=[HumanMessage('current intent'),AIMessage('',tool_calls=calls),ToolMessage('one',tool_call_id='0'),ToolMessage('two',tool_call_id='1')]
        with patch.dict(os.environ,{'CORA_CONTEXT_TOKENS':'4096'}):
            result=fit_messages([SystemMessage('identity'),HumanMessage('x'*7000),AIMessage('old')]+turn,reserve=1024)
        self.assertEqual(result[1:],turn)

    def test_partial_or_duplicate_tool_exchange_cannot_reach_model(self):
        call=AIMessage('',tool_calls=[{'id':'a','name':'read','args':{}}])
        for rest in [[],[ToolMessage('one',tool_call_id='b')],[ToolMessage('one',tool_call_id='a'),ToolMessage('again',tool_call_id='a')]]:
            with self.assertRaises(ContextOverflow):fit_messages([HumanMessage('request'),call]+rest)

    def test_optional_data_cannot_displace_current_intent(self):
        summary=HumanMessage('x'*7000,name='conversation_summary')
        with patch.dict(os.environ,{'CORA_CONTEXT_TOKENS':'4096'}):
            result=fit_messages([SystemMessage('identity'),summary,HumanMessage('intent')],reserve=1024)
        self.assertEqual([m.content for m in result],['identity','intent'])

    def test_current_intent_is_not_dropped_to_keep_large_tool_result(self):
        with patch.dict(os.environ,{'CORA_CONTEXT_TOKENS':'4096'}):
            with self.assertRaises(ContextOverflow):fit_messages([HumanMessage('x'*6000),AIMessage('',tool_calls=[{'id':'a','name':'read','args':{}}]),ToolMessage('small',tool_call_id='a')],reserve=1024)

    def test_owner_context_is_not_injected_into_every_prompt(self):
        from core.prompt_context import with_permanent_context
        rendered = with_permanent_context('base')
        self.assertIn('base', rendered)
        self.assertIn('CURRENT SERVER TIME', rendered)
        self.assertNotIn('PERMANENT USER-CONFIGURED CONTEXT', rendered)

    def test_owner_context_is_loaded_only_through_explicit_tool(self):
        import tools
        with patch('tools.get_system_context', return_value={'version':3,'content':'owner one','updated_at':None}) as get:
            with patch('tools._require_supervisor_permission'):
                result = json.loads(tools.owner_context_tool.func())
        self.assertEqual(result['version'],3)
        self.assertEqual(result['content'],'owner one')
        get.assert_called_once()


@unittest.skipUnless(os.getenv('CORA_RUNTIME_TEST_DATABASE_URL'),'Requires disposable PostgreSQL+pgvector')
class MemoryPostgresTests(unittest.TestCase):
    def setUp(self):
        with db_connection() as c:c.execute('TRUNCATE memories,context_jobs,conversation_summaries,action_approvals,tool_policies CASCADE')
        import core.permissions as permissions
        permissions._policy_time=0

    def tearDown(self):
        from core.database import close_pool
        close_pool()

    def test_versioned_edit_and_stale_write_preserve_previous_content(self):
        with patch('core.memory.embed_text') as embed:
            first=save_memory(memory_type='fact',key='owner',content='Original')
            second=save_memory(memory_type='fact',key='owner',content='Corrected',expected_version=1,expected_memory_id=str(first['id']))
            with self.assertRaises(MemoryConflict):save_memory(memory_type='fact',key='owner',content='Stale',expected_version=1,expected_memory_id=str(first['id']))
            embed.assert_not_called()
        history=memory_history(str(first['id']))
        self.assertEqual([h['snapshot']['content'] for h in history],['Corrected','Original'])
        self.assertEqual(second['version'],2)

    def test_owner_update_requires_exact_version_approval_even_with_auto_policy(self):
        from tools import remember_tool
        from core.permissions import set_policy
        from core.governance import resolve
        first=save_memory(memory_type='fact',key='owner',content='Original')
        set_policy('supervisor','remember_memory','auto')
        args={'memory_type':'fact','key':'owner','content':'Hypothesis','expected_version':1,'expected_memory_id':str(first['id']),'assertion':'inference','confidence':0.6}
        proposal=json.loads(remember_tool.invoke(args))
        self.assertEqual(proposal['status'],'pending')
        self.assertEqual(memory_history(str(first['id']))[0]['snapshot']['content'],'Original')
        resolve(proposal['approval_id'],True,'Ale')
        history=memory_history(str(first['id']))
        self.assertEqual(history[0]['snapshot']['content'],'Hypothesis')
        self.assertEqual(history[0]['snapshot']['owner_kind'],'user')
        self.assertEqual(history[0]['snapshot']['assertion'],'inference')

    def test_changed_owner_version_invalidates_approved_correction(self):
        from tools import remember_tool
        from core.permissions import set_policy
        from core.governance import resolve
        first=save_memory(memory_type='fact',key='owner',content='Original')
        set_policy('supervisor','remember_memory','auto')
        proposal=json.loads(remember_tool.invoke({'memory_type':'fact','key':'owner','content':'Outdated proposal','expected_version':1,'expected_memory_id':str(first['id'])}))
        save_memory(memory_type='fact',key='owner',content='New user edit',expected_version=1,expected_memory_id=str(first['id']))
        with self.assertRaises(RuntimeError):resolve(proposal['approval_id'],True,'Ale')
        self.assertEqual(memory_history(str(first['id']))[0]['snapshot']['content'],'New user edit')

    def test_agent_cannot_delete_owner_memory_to_bypass_correction_approval(self):
        from tools import forget_memory_tool
        from core.permissions import set_policy
        first=save_memory(memory_type='note',key='owner',content='Keep')
        set_policy('supervisor','forget_memory','auto')
        outcome=json.loads(forget_memory_tool.invoke({'memory_id':str(first['id']),'expected_version':1}))
        self.assertEqual(outcome['status'],'pending')
        self.assertEqual(len(memory_history(str(first['id']))),1)

    def test_inference_expiry_and_model_provenance(self):
        from tools import remember_tool
        from core.permissions import set_policy
        set_policy('supervisor','remember_memory','auto')
        outcome=json.loads(remember_tool.invoke({'memory_type':'note','key':'guess','content':'Possible preference','confidence':0.4}))
        self.assertEqual(outcome['assertion'],'inference');self.assertEqual(outcome['owner_kind'],'agent')
        with db_connection() as c:c.execute("UPDATE memories SET expires_at=NOW()-INTERVAL '1 second' WHERE key='guess'")
        self.assertEqual(search_memories(),[])
        self.assertEqual(len(memory_history(outcome['id'])),1)

    def test_partial_large_summary_never_commits_a_false_boundary(self):
        cid=uuid4();old_id=uuid4();text='abé😀'*9000
        with db_connection() as c:
            c.execute('INSERT INTO conversations (id) VALUES (%s)',(cid,))
            c.execute("INSERT INTO messages(id,conversation_id,role,content,created_at) VALUES(%s,%s,'user',%s,NOW()-INTERVAL '1 day')",(old_id,cid,text))
            c.execute("INSERT INTO messages(id,conversation_id,role,content) VALUES(%s,%s,'user','recent')",(uuid4(),cid))
        seen=[]
        class Model:
            def invoke(self,messages,**kwargs):
                seen.extend(m['content'] for m in json.loads(messages[-1].content)['messages'])
                return AIMessage('summary')
        with patch('core.models.get_chat_model',return_value=Model()):
            with self.assertRaises(ContextDeferred):prepare_context(str(cid),should_yield=lambda:bool(seen))
            with db_connection() as c:self.assertIsNone(c.execute('SELECT * FROM conversation_summaries WHERE conversation_id=%s',(cid,)).fetchone())
            seen.clear();context=prepare_context(str(cid))
        self.assertEqual(''.join(seen),text)
        self.assertEqual(context[-1]['content'],'recent')

    def test_background_embedding_cannot_attach_to_a_changed_memory_version(self):
        from core.background_embeddings import index_pending_once,runtime
        first=save_memory(memory_type='note',key='embedding',content='Old')
        def changed(_):
            save_memory(memory_type='note',key='embedding',content='New',expected_version=1,expected_memory_id=str(first['id']))
            return [[1.0,2.0]]
        with patch.object(runtime,'last_foreground',0),patch.object(runtime,'snapshot',return_value=[]),patch('core.background_embeddings.EMBEDDING_MODEL','test'),patch('core.background_embeddings.embed_batch',side_effect=changed):
            self.assertTrue(index_pending_once())
        with db_connection() as c:row=c.execute('SELECT * FROM memories WHERE id=%s',(first['id'],)).fetchone()
        self.assertEqual(row['version'],2);self.assertIsNone(row['embedding'])

    def test_summary_pages_history_without_skipping_messages(self):
        cid=uuid4()
        with db_connection() as c:
            c.execute('INSERT INTO conversations(id) VALUES(%s)',(cid,))
            for i in range(150):
                c.execute("INSERT INTO messages(id,conversation_id,role,content,created_at) VALUES(%s,%s,'user',%s,NOW()+(%s * INTERVAL '1 second'))",(uuid4(),cid,str(i),i))
        seen=[]
        class Model:
            def invoke(self,messages,**kwargs):
                seen.extend(m['content'] for m in json.loads(messages[-1].content)['messages'])
                return AIMessage('summary')
        with patch('core.models.get_chat_model',return_value=Model()):context=prepare_context(str(cid))
        self.assertEqual(seen+[m['content'] for m in context if m.get('name')!='conversation_summary'],[str(i) for i in range(150)])

    def test_owner_api_rejects_stale_edits_and_preserves_actor_provenance(self):
        from fastapi.testclient import TestClient
        from core.auth import provision
        import api
        with db_connection() as c:c.execute('TRUNCATE app_sessions,app_users CASCADE')
        provision('Ale','a-long-local-password')
        with TestClient(api.app,headers={'X-Cora-Client':'ui'}) as client:
            self.assertEqual(client.post('/auth/login',json={'username':'Ale','password':'a-long-local-password'}).status_code,200)
            body={'memory_type':'note','key':'api','content':'Original','source':'assistant_selected','metadata':{'editor':'agent','source_ref':'forged'}}
            first=client.post('/memory',json=body)
            self.assertEqual(first.status_code,200,first.text)
            self.assertEqual(first.json()['source'],'user_explicit')
            self.assertEqual(first.json()['metadata']['editor'],'user')
            self.assertIsNone(first.json()['metadata']['source_ref'])
            self.assertEqual(client.post('/memory',json={**body,'content':'Unexpected'}).status_code,409)
            second=client.post('/memory',json={**body,'content':'Explicit edit','expected_version':1,'expected_memory_id':first.json()['id']})
            self.assertEqual(second.status_code,200,second.text)
            self.assertEqual(client.post('/memory',json={**body,'expected_version':1,'expected_memory_id':first.json()['id']}).status_code,409)
            history=client.get('/memory/'+first.json()['id']+'/history').json()
            self.assertEqual([v['snapshot']['content'] for v in history],['Explicit edit','Original'])
            context=client.get('/memory/context').json()
            updated=client.put('/memory/context',json={'content':'Owner rules','expected_version':context['version']})
            self.assertEqual(updated.status_code,200,updated.text)
            self.assertEqual(client.put('/memory/context',json={'content':'Stale','expected_version':context['version']}).status_code,409)

    def test_delete_and_recreate_same_key_cannot_retarget_a_previous_proposal(self):
        from tools import remember_tool
        from core.permissions import set_policy
        from core.governance import resolve
        from core.memory import delete_memory
        first=save_memory(memory_type='note',key='recreated',content='Original')
        set_policy('supervisor','remember_memory','auto')
        proposal=json.loads(remember_tool.invoke({'memory_type':'note','key':'recreated','content':'Old correction','expected_version':1,'expected_memory_id':str(first['id'])}))
        self.assertTrue(delete_memory(str(first['id'])))
        replacement=save_memory(memory_type='note',key='recreated',content='Entirely new memory')
        with self.assertRaises(RuntimeError):resolve(proposal['approval_id'],True,'Ale')
        self.assertEqual(memory_history(str(replacement['id']))[0]['snapshot']['content'],'Entirely new memory')
