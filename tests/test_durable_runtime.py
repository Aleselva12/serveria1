"""Fault injection and disposable PostgreSQL tests for durable execution."""
import os
import threading
import tempfile
from pathlib import Path
import unittest
from uuid import uuid4
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.runtime import Runtime, Run, current_run
from core.run_states import DurabilityLost
from core.governance import agent_tool, execute_capability, executables
from core.database import db_connection
from core.run_lifecycle import create_run, transition_run, get_run, recover, request_cancel, RunConflict
from core.operation_journal import get_operation, list_operations, review, begin

class DurabilityUnitTests(unittest.TestCase):
    def test_failed_admission_never_registers_or_starts_work(self):
        runtime = Runtime(); effects=[]
        with patch('core.run_lifecycle.create_run',side_effect=OSError('private details')):
            with self.assertRaises(OSError): runtime.submit('not-admitted',lambda run:effects.append(True))
        self.assertEqual(runtime.runs,{})
        self.assertEqual(effects,[])

    def test_failed_running_transition_aborts_before_callback_and_closes_runtime(self):
        runtime = Runtime(); effects=[]
        with patch('core.run_lifecycle.create_run'),patch('core.run_lifecycle.transition_run',side_effect=OSError('private details')):
            run = runtime.submit('not-started',lambda run:effects.append(True))
            self.assertTrue(run.done.wait(2))
        self.assertEqual(effects,[])
        self.assertEqual(run.status,'interrupted')
        self.assertEqual(run.error_type,'DurabilityLost')
        self.assertIsNotNone(run.persistence_error)
        with self.assertRaises(RuntimeError): runtime.submit('next',lambda run:{})

@unittest.skipUnless(os.getenv('CORA_RUNTIME_TEST_DATABASE_URL'),'Requires disposable PostgreSQL+pgvector')
class DurablePostgresTests(unittest.TestCase):
    def setUp(self):
        with db_connection() as c: c.execute('TRUNCATE capability_operations,runtime_runs,action_approvals CASCADE')
        self.runtime = Runtime()
        self.keys=set(executables)
        self.policy = patch('core.permissions.policy_overrides',return_value={('supervisor','remember_memory'):'auto'})
        self.policy.start()
    def tearDown(self):
        self.runtime.shutdown();self.policy.stop()
        for key in set(executables)-self.keys: executables.pop(key)

    def test_canonical_result_survives_worker_eviction_and_terminal_rows_are_immutable(self):
        result={'response':'saved result','thread_id':'durable'}
        run=self.runtime.submit('durable',lambda run:result)
        self.assertTrue(run.done.wait(3));self.assertEqual(run.status,'completed')
        row=get_run(run.id);self.assertEqual(row['result'],result)
        same=transition_run(run.id,'completed',metadata={'overwrite':True},result={'response':'changed'})
        self.assertEqual(same['revision'],row['revision']);self.assertEqual(same['result'],result)
        self.assertNotIn('overwrite',same['metadata'])
        with self.assertRaises(RunConflict): transition_run(run.id,'running')
        from core.runtime_api import router
        app=FastAPI();app.include_router(router)
        with patch('core.runtime_api.runtime',Runtime()),TestClient(app) as client:
            restored=client.get('/api/v1/runtime/runs/'+run.id)
            self.assertEqual(restored.status_code,200);self.assertEqual(restored.json()['result'],result)
            events=client.get('/api/v1/runtime/runs/'+run.id+'/events')
            self.assertIn('event: result',events.text);self.assertIn('saved result',events.text)

    def test_cancel_keeps_known_effect_and_blocks_identical_inflight_operation(self):
        started, release=threading.Event(),threading.Event(); effects=[]
        @agent_tool('supervisor',actions=('remember_memory',),effect='write',retry='never')
        def durable_cancel_write(value:str)->str:
            """A blocking write whose effect is known when the function returns."""
            effects.append(value);started.set();release.wait(3);return 'saved'
        run=self.runtime.submit('cancel-write',lambda run:{'response':durable_cancel_write.invoke({'value':'one'})})
        try:
            self.assertTrue(started.wait(2))
            conflict=execute_capability('supervisor.durable_cancel_write',{'value':'one'})
            self.assertEqual(conflict.error.code,'OperationConflict');self.assertEqual(effects,['one'])
            with patch('core.runtime.runtime',self.runtime): request_cancel(run.id)
            self.assertEqual(run.status,'cancelling');self.assertFalse(run.done.is_set())
            next_run=self.runtime.submit('next',lambda run:{})
            self.assertEqual(next_run.status,'queued')
        finally: release.set()
        self.assertTrue(run.done.wait(3));self.assertTrue(next_run.done.wait(3))
        self.assertEqual(run.status,'cancelled')
        self.assertEqual(get_run(run.id)['stop_reason'],'cancelled')
        operations=list_operations(run_id=run.id)
        self.assertEqual(operations[0]['status'],'succeeded');self.assertEqual(effects,['one'])

    def test_recovery_marks_only_unknown_writes_uncertain_and_never_replays(self):
        root=create_run(thread_id='recover');root_id=str(root['id'])
        child=create_run(thread_id='child',parent_run_id=root_id,kind='component',target='audio_agent')
        child_id=str(child['id'])
        for id in [root_id,child_id]:transition_run(id,'running')
        @agent_tool('supervisor',actions=('remember_memory',),effect='write',retry='never')
        def recovery_write(value:str)->str:
            """Must never run during recovery."""
            self.fail('Recovery replayed an effect')
        @agent_tool('supervisor',actions=('calculate',),effect='read',retry='safe')
        def recovery_read()->str:
            """Recovery does not replay reads either."""
            self.fail('Recovery replayed a read')
        root_run=Run('recover',id=root_id,durable=True)
        token=current_run.set(root_run)
        try:
            write_entry=next(e for e in executables.values() if e['tool'] is recovery_write)
            read_entry=next(e for e in executables.values() if e['tool'] is recovery_read)
            write=begin(write_entry,{'value':'one'});read=begin(read_entry,{})
        finally: current_run.reset(token)
        approval_id=uuid4()
        with db_connection() as c:
            c.execute("INSERT INTO action_approvals (id,actor,action,tool_id,payload,status) VALUES (%s,'supervisor','remember_memory','old','{}','executing')",(approval_id,))
        self.assertEqual(recover(),2);self.assertEqual(recover(),0)
        self.assertEqual(get_operation(write)['status'],'uncertain')
        self.assertEqual(get_operation(read)['status'],'failed')
        self.assertEqual(get_run(root_id)['status'],'interrupted')
        self.assertEqual(get_run(child_id)['status'],'interrupted')
        with db_connection() as c:status=c.execute('SELECT status FROM action_approvals WHERE id=%s',(approval_id,)).fetchone()['status']
        self.assertEqual(status,'uncertain')

    def test_uncertain_effect_requires_review_before_a_new_explicit_attempt(self):
        effects=[]
        @agent_tool('supervisor',actions=('remember_memory',),effect='write',retry='never')
        def partial_write(value:str)->str:
            """A failure can occur after an external effect."""
            effects.append(value)
            if len(effects)==1:raise OSError('private detail')
            return 'saved'
        first=execute_capability('supervisor.partial_write',{'value':'one'})
        self.assertEqual(first.error.code,'EffectUncertain')
        operation=get_operation(first.operation_id);self.assertEqual(operation['status'],'uncertain')
        blocked=execute_capability('supervisor.partial_write',{'value':'one'})
        self.assertEqual(blocked.error.code,'OperationConflict');self.assertEqual(effects,['one'])
        with self.assertRaises(ValueError):review(first.operation_id,'effect_verified','','Ale')
        review(first.operation_id,'effect_verified','Verificato il file risultante','Ale')
        self.assertEqual(effects,['one'])
        with self.assertRaises(ValueError):review(first.operation_id,'no_effect_verified','Seconda verifica','Ale')
        retried=execute_capability('supervisor.partial_write',{'value':'one'})
        self.assertEqual(retried.status,'ok');self.assertEqual(effects,['one','one'])
        self.assertEqual(get_operation(first.operation_id)['status'],'uncertain')
        self.assertEqual(get_operation(first.operation_id)['reviewed_by'],'Ale')

    def test_journal_outage_before_effect_prevents_execution(self):
        effects=[]
        @agent_tool('supervisor',actions=('remember_memory',),effect='write',retry='never')
        def journal_start_test()->str:
            """Cannot act unless the intent is committed."""
            effects.append(True);return 'ok'
        with patch('core.operation_journal.db_connection',side_effect=OSError('private detail')):
            with self.assertRaises(DurabilityLost):execute_capability('supervisor.journal_start_test',{})
        self.assertEqual(effects,[])

    def test_lost_journal_outcome_stops_reasoning_and_keeps_uncertainty_after_restart(self):
        effects=[];continued=[]
        @agent_tool('supervisor',actions=('remember_memory',),effect='write',retry='never')
        def journal_finish_test()->str:
            """Effect returns but recording its outcome fails."""
            effects.append(True);return 'ok'
        def work(run):
            journal_finish_test.invoke({});continued.append(True);return {}
        with patch('core.operation_journal.finish',side_effect=DurabilityLost('OutcomeNotPersisted')):
            run=self.runtime.submit('journal-lost',work);self.assertTrue(run.done.wait(3))
        self.assertEqual(effects,[True]);self.assertEqual(continued,[])
        self.assertEqual(run.status,'interrupted');self.assertTrue(self.runtime.closed)
        self.assertEqual(list_operations(run_id=run.id)[0]['status'],'started')
        recover()
        self.assertEqual(list_operations(run_id=run.id)[0]['status'],'uncertain')

    def test_lost_run_completion_preserves_known_operation_without_replay(self):
        effects=[]
        @agent_tool('supervisor',actions=('remember_memory',),effect='write',retry='never')
        def known_write()->str:
            """Known success survives a separate run persistence failure."""
            effects.append(True);return 'ok'
        real_transition=transition_run
        def fail_completion(id,status,**kwargs):
            if status=='completed':raise OSError('Completion unavailable')
            return real_transition(id,status,**kwargs)
        with patch('core.run_lifecycle.transition_run',side_effect=fail_completion):
            run=self.runtime.submit('run-completion-lost',lambda run:{'response':known_write.invoke({})})
            self.assertTrue(run.done.wait(3))
        self.assertEqual(run.status,'interrupted');self.assertEqual(get_run(run.id)['status'],'running')
        self.assertEqual(list_operations(run_id=run.id)[0]['status'],'succeeded')
        with self.assertRaises(RuntimeError):self.runtime.submit('new',lambda run:{})
        recover();self.assertEqual(get_run(run.id)['status'],'interrupted');self.assertEqual(effects,[True])

    def test_commit_acknowledgement_loss_preserves_canonical_completion(self):
        real_transition=transition_run
        def lose_acknowledgement(id,status,**kwargs):
            row=real_transition(id,status,**kwargs)
            if status=='completed':raise OSError('Commit acknowledgement lost')
            return row
        with patch('core.run_lifecycle.transition_run',side_effect=lose_acknowledgement):
            run=self.runtime.submit('committed-but-unacknowledged',lambda run:{'response':'persisted'})
            self.assertTrue(run.done.wait(3))
        self.assertEqual(run.status,'interrupted');self.assertTrue(self.runtime.closed)
        self.assertEqual(get_run(run.id)['status'],'completed')
        recover()
        self.assertEqual(get_run(run.id)['result'],{'response':'persisted'})

    def test_calendar_proposal_is_an_awaiting_approval_run_with_a_pending_operation(self):
        from core.calendar_tools import calendar_tools_for
        tool=next(t for t in calendar_tools_for('supervisor') if t.name=='calendar_create_event')
        data=dict(title='Verifica run',start='2026-10-05T10:00:00+02:00',end='2026-10-05T11:00:00+02:00')
        with patch('core.permissions.policy_overrides',return_value={('supervisor','calendar_create_event'):'confirm'}):
            run=self.runtime.submit('calendar-pending',lambda run:{'response':tool.invoke(data)})
            self.assertTrue(run.done.wait(3))
        self.assertEqual(run.status,'awaiting_approval')
        row=get_run(run.id);self.assertEqual(len(row['approval_ids']),1)
        operation=list_operations(run_id=run.id)[0]
        self.assertEqual(operation['status'],'pending')
        self.assertEqual(operation['result']['approval_id'],row['approval_ids'][0])

    def test_delegated_proposal_persists_child_result_and_awaiting_approval(self):
        from core.calendar_tools import calendar_tools_for
        from tools import _delegate_agent
        from langchain_core.messages import AIMessage
        tool=next(t for t in calendar_tools_for('email_quotes_agent') if t.name=='calendar_create_event')
        class Graph:
            def stream(self,state,**kwargs):
                tool.invoke(dict(title='Proposta delegata',start='2026-10-05T12:00:00+02:00',end='2026-10-05T13:00:00+02:00'))
                yield 'values',{'messages':[AIMessage(content='Proposta da confermare')]}
        @agent_tool('supervisor',actions=('delegate_email',),effect='delegate',retry='never')
        def durable_delegate()->str:
            """A delegated run can finish its reasoning while an approval remains pending."""
            return _delegate_agent(target='email_quotes_agent',capability='email',query='Organizza appuntamento',thread_id='',graph_loader=Graph)
        with patch('core.permissions.policy_overrides',return_value={('supervisor','delegate_email'):'auto',('email_quotes_agent','calendar_create_event'):'confirm'}):
            run=self.runtime.submit('delegated-pending',lambda run:{'response':durable_delegate.invoke({})})
            self.assertTrue(run.done.wait(3))
        self.assertEqual(run.status,'awaiting_approval')
        with db_connection() as c:
            child=c.execute('SELECT * FROM runtime_runs WHERE parent_run_id=%s',(run.id,)).fetchone()
        self.assertEqual(child['status'],'awaiting_approval')
        self.assertEqual(child['result']['content'],'Proposta da confermare')
        self.assertEqual(child['approval_ids'],get_run(run.id)['approval_ids'])
        operations=list_operations(run_id=run.id)
        pending=next(o for o in operations if o['status']=='pending')
        self.assertEqual(str(pending['run_id']),str(child['id']))
        self.assertEqual(str(pending['root_run_id']),run.id)

    def test_committed_cancel_is_checked_at_the_effect_boundary(self):
        from core.run_lifecycle import mark_stop
        from core.runtime import RunStopped
        root=create_run(thread_id='cancel-before-effect');id=str(root['id']);transition_run(id,'running')
        effects=[]
        @agent_tool('supervisor',actions=('remember_memory',),effect='write',retry='never')
        def cancel_boundary_write()->str:
            """Cancellation committed before dispatch prevents effects."""
            effects.append(True);return 'ok'
        mark_stop(id,'cancelled')
        token=current_run.set(Run('cancel-before-effect',id=id,status='running',durable=True))
        try:
            with self.assertRaises(RunStopped):execute_capability('supervisor.cancel_boundary_write',{})
        finally:current_run.reset(token)
        self.assertEqual(effects,[]);self.assertEqual(list_operations(run_id=id),[])

    def test_owner_review_api_is_strict_and_cannot_change_the_recorded_actor(self):
        from core.runtime_api import router
        from core.auth import AuthMiddleware
        @agent_tool('supervisor',actions=('remember_memory',),effect='write',retry='never')
        def review_api_write()->str:
            """An uncertain effect requires owner evidence."""
            raise OSError('Outcome unknown')
        operation=execute_capability('supervisor.review_api_write',{}).operation_id
        app=FastAPI();app.include_router(router);app.add_middleware(AuthMiddleware)
        path='/api/v1/runtime/operations/'+operation+'/review'
        with patch('core.auth.session_user',return_value={'id':'owner','username':'Ale'}),TestClient(app,headers={'X-Cora-Client':'ui'}) as client:
            bad=client.post(path,json={'outcome':'no_effect_verified','note':'Verificato','actor':'other'})
            self.assertEqual(bad.status_code,422)
            self.assertIsNone(get_operation(operation)['reviewed_by'])
            good=client.post(path,json={'outcome':'no_effect_verified','note':'Verificata assenza di effetto'})
            self.assertEqual(good.status_code,200);self.assertEqual(good.json()['reviewed_by'],'Ale')
            again=client.post(path,json={'outcome':'effect_verified','note':'Seconda richiesta'})
            self.assertEqual(again.status_code,409)

    def test_trace_failure_does_not_change_canonical_success(self):
        with tempfile.TemporaryDirectory() as directory, patch('core.execution_traces.TRACE_FILE',Path(directory)):
            run=self.runtime.submit('trace-lost',lambda run:{'response':'known result'})
            self.assertTrue(run.done.wait(3))
            self.assertEqual(run.status,'completed')
            self.assertEqual(get_run(run.id)['result'],{'response':'known result'})
            from core.execution_traces import trace_status
            self.assertEqual(trace_status()['write_error'],'IsADirectoryError')

    def test_child_cancellation_marks_root_and_all_descendants(self):
        root=create_run(thread_id='root');root_id=str(root['id'])
        child=create_run(thread_id='child',parent_run_id=root_id);child_id=str(child['id'])
        sibling=create_run(thread_id='sibling',parent_run_id=root_id);sibling_id=str(sibling['id'])
        grandchild=create_run(thread_id='grandchild',parent_run_id=child_id);grandchild_id=str(grandchild['id'])
        for id in [root_id,child_id,sibling_id,grandchild_id]:transition_run(id,'running')
        request_cancel(child_id)
        for id in [root_id,child_id,sibling_id,grandchild_id]:
            row=get_run(id);self.assertTrue(row['cancel_requested']);self.assertEqual(row['stop_reason'],'cancelled')
