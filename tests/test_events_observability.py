"""Diagnostics are lossy metadata; critical facts share the canonical transaction."""
import json
import os
import tempfile
import threading
import time
import unittest
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.protocol import ComponentEvent
from core.observability import DiagnosticArchive,metadata_event,prune,read as read_diagnostics
from core.event_bus import EventBus
from core.database import db_connection
from core.run_lifecycle import create_run,transition_run,get_run,recover
from core.domain_events import read as read_critical


class DiagnosticUnitTests(unittest.TestCase):
    def test_payload_projection_and_tokens_never_enter_archive(self):
        event=ComponentEvent(type='tool.finished',source='test',payload={'capability_id':'test.read','duration_ms':10,'prompt':'secret','args':{'password':'secret'},'result':'secret','error':'secret'})
        self.assertNotIn('secret',json.dumps(metadata_event(event.model_dump())))
        self.assertIsNone(metadata_event(ComponentEvent(type='chat.delta',source='test',payload={'text':'secret'}).model_dump()))
        recorder=DiagnosticArchive();recorder.record(ComponentEvent(type='log.failure',source='test',payload={'error':'secret','error_type':'OSError'}).model_dump())
        self.assertNotIn('secret',json.dumps(list(recorder.queue)))
        malformed=ComponentEvent(type='memory.selected',source='test',payload={'references':[{'id':'secret','version':{'body':'secret'}}]}).model_dump()
        self.assertEqual(metadata_event(malformed)['payload']['references'],[])
        malformed=ComponentEvent(type='log.failure',source='test',payload={'result_count':{'body':'secret'}}).model_dump()
        self.assertNotIn('secret',json.dumps(metadata_event(malformed)))

    def test_queue_is_bounded_and_freezes_payload_without_database_io(self):
        recorder=DiagnosticArchive(1)
        event=ComponentEvent(type='context.selected',source='test',payload={'optional_included':['conversation_summary']}).model_dump()
        with patch('core.observability.db_connection') as db:
            recorder.record(event);event['payload']['optional_included'].clear();recorder.record(event);db.assert_not_called()
        self.assertEqual(recorder.status()['dropped'],1)
        self.assertEqual(recorder.queue[0]['payload']['optional_included'],['conversation_summary'])

    def test_database_failure_keeps_pending_diagnostics_and_exposes_health(self):
        recorder=DiagnosticArchive();recorder.record(ComponentEvent(type='run.state',source='test',payload={'status':'running'}).model_dump())
        with patch('core.observability.database_configured',return_value=True),patch('core.observability.db_connection',side_effect=OSError('secret')):
            self.assertFalse(recorder.flush())
        self.assertEqual(recorder.status()['pending'],1)
        self.assertEqual(recorder.status()['last_error'],'OSError')
        self.assertNotIn('secret',json.dumps(recorder.status()))

    def test_failed_diagnostic_sink_cannot_break_live_bus(self):
        bus=EventBus(2)
        with patch('core.observability.archive.record',side_effect=OSError('secret')):
            bus.publish('test','test',run_id='run')
        self.assertEqual(len(bus.read(0,'run')[0]),1)
        self.assertTrue(bus.read(100)[1])
        events,gap,watermark=bus.read_window(0,'another')
        self.assertEqual(events,[]);self.assertEqual(watermark,1)

    def test_log_file_failure_cannot_invalidate_completed_work_or_store_exception_text(self):
        from core.logging import logged_operation
        from core.observability import archive
        with tempfile.TemporaryDirectory() as directory,patch('core.logging.LOG_FILE',Path(directory)):
            with logged_operation('test',component='test',data={'prompt':'secret'}) as context:context['result']={'response':'secret'}
            with self.assertRaises(OSError):
                with logged_operation('test_error',component='test'):raise OSError('secret')
        self.assertNotIn('secret',json.dumps(list(archive.queue)))
        with patch('core.event_bus.bus.publish',side_effect=OSError('secret')):
            with logged_operation('failed_sink',component='test'):pass
            with self.assertRaisesRegex(ValueError,'original'):
                with logged_operation('failed_sink',component='test'):raise ValueError('original')

    def test_model_first_token_is_per_invocation_and_errors_leave_no_busy_agent(self):
        from core.runtime import Run,current_run
        from core.execution_traces import ExecutionTrace
        from langchain_core.outputs import LLMResult,ChatGeneration
        from langchain_core.messages import AIMessage
        run=Run('thread');token=current_run.set(run)
        try:
            trace=ExecutionTrace('thread','v1');span=uuid4()
            trace.on_chat_model_start({},[],run_id=span,metadata={'cora_role':'research'})
            trace.on_llm_new_token('text',run_id=span)
            trace.on_llm_end(LLMResult(generations=[[ChatGeneration(message=AIMessage('secret',response_metadata={'eval_count':2,'eval_duration':1000000}))]]),run_id=span)
            self.assertGreaterEqual(run.timings['models'][0]['first_token_ms'],0)
            failed=uuid4();trace.on_chat_model_start({},[],run_id=failed,metadata={'cora_role':'email'})
            trace.on_llm_error(OSError('secret'),run_id=failed)
            self.assertEqual(run.agents['email'],'idle')
            self.assertIsNone(run.timings['models'][1]['first_token_ms'])
            self.assertNotIn('secret',json.dumps(run.timings))
        finally:current_run.reset(token)

    def test_stream_resets_invalid_future_or_foreign_process_cursor_once(self):
        from core.runtime import Runtime,publish_text
        from core.runtime_api import router
        runtime=Runtime(persistent=False)
        run=runtime.submit('stream',lambda run:{'response':'canonical'})
        self.assertTrue(run.done.wait(2));publish_text(run,'test','span','known output')
        app=FastAPI();app.include_router(router)
        with patch('core.runtime_api.runtime',runtime),TestClient(app) as client:
            for cursor in ['invalid',str(uuid4())+':9000']:
                response=client.get('/api/v1/runtime/runs/'+run.id+'/events',headers={'Last-Event-ID':cursor})
                self.assertEqual(response.text.count('event: resync'),1)
                self.assertIn('known output',response.text);self.assertIn('event: result',response.text)
                self.assertNotIn('chat.delta',response.text)
            self.assertEqual(client.get('/api/v1/runtime/runs/'+run.id+'/events?after=-1').status_code,422)
        runtime.shutdown()


@unittest.skipUnless(os.getenv('CORA_RUNTIME_TEST_DATABASE_URL'),'Requires disposable PostgreSQL+pgvector')
class EventPostgresTests(unittest.TestCase):
    def setUp(self):
        with db_connection() as conn:conn.execute('TRUNCATE diagnostic_events')

    def tearDown(self):
        from core.database import close_pool
        close_pool()

    @unittest.skipIf(os.getenv('CORA_DB_POOL_SIZE')=='1','Requires concurrent real PostgreSQL connections')
    def test_critical_cursor_follows_commit_order(self):
        from core.domain_events import append
        acquired=threading.Event();attempted=threading.Event();release=threading.Event();finished=threading.Event()
        errors=[];ids=[uuid4(),uuid4()]
        def first():
            try:
                with db_connection() as conn:
                    append(conn,type='test.commit',source='test',aggregate_id=ids[0],revision=1)
                    acquired.set()
                    if not release.wait(5):raise AssertionError('Commit release timed out')
            except Exception as error:errors.append(error)
        def second():
            try:
                with db_connection() as conn:
                    attempted.set()
                    append(conn,type='test.commit',source='test',aggregate_id=ids[1],revision=1)
                finished.set()
            except Exception as error:errors.append(error)
        a=threading.Thread(target=first);b=threading.Thread(target=second)
        a.start()
        try:
            self.assertTrue(acquired.wait(3));b.start()
            self.assertTrue(attempted.wait(3));self.assertFalse(finished.wait(.1))
        finally:
            release.set();a.join(5)
            if b.ident is not None:b.join(5)
        self.assertFalse(a.is_alive());self.assertFalse(b.is_alive());self.assertEqual(errors,[])
        with db_connection() as conn:
            rows=conn.execute('SELECT aggregate_id FROM domain_events WHERE aggregate_id=ANY(%s) ORDER BY sequence',(ids,)).fetchall()
        self.assertEqual([r['aggregate_id'] for r in rows],ids)

    def test_critical_failure_rolls_back_state_and_event_together(self):
        run=create_run(thread_id='atomic');id=str(run['id'])
        before=read_critical(run_id=id)['events']
        with patch('core.domain_events.run_state',side_effect=OSError('critical store failed')):
            with self.assertRaises(OSError):transition_run(id,'running')
        self.assertEqual(get_run(id)['status'],'queued')
        self.assertEqual(read_critical(run_id=id)['events'],before)

    def test_committed_events_correlate_children_and_survive_recovery(self):
        root=create_run(thread_id='root');id=str(root['id'])
        child=create_run(thread_id='child',parent_run_id=id);cid=str(child['id'])
        transition_run(id,'running');transition_run(cid,'running');recover()
        events=read_critical(run_id=id)['events']
        self.assertTrue(any(e['component_run_id']==cid and e['payload']['status']=='interrupted' for e in events))
        self.assertTrue(all(e['run_id']==id for e in events))
        first=read_critical(run_id=id,limit=2)
        remaining=read_critical(run_id=id,after=first['next_cursor'])
        self.assertEqual(first['events']+remaining['events'],events)

    def test_operation_journal_commits_only_metadata_and_review_is_a_fact_not_replay(self):
        from core.governance import agent_tool,execute_capability
        from core.operation_journal import review,get_operation
        @agent_tool('supervisor',actions=('calculate',),effect='write',retry='never')
        def event_test_write(secret:str)->str:
            """A failed external write has an uncertain result."""
            raise OSError('secret exception')
        with patch('core.permissions.policy_overrides',return_value={('supervisor','calculate'):'auto'}):
            operation=execute_capability('supervisor.event_test_write',{'secret':'private argument'}).operation_id
        review(operation,'no_effect_verified','private review note','Ale')
        with db_connection() as conn:events=conn.execute('SELECT event FROM domain_events WHERE aggregate_id=%s ORDER BY sequence',(uuid4() if not operation else operation,)).fetchall()
        self.assertEqual([e['event']['type'] for e in events],['operation.committed','operation.committed','operation.reviewed'])
        self.assertNotIn('private',json.dumps(events));self.assertNotIn('secret exception',json.dumps(events))
        self.assertEqual(get_operation(operation)['status'],'uncertain')

    def test_diagnostic_retry_is_idempotent_and_retention_never_deletes_critical_facts(self):
        root=create_run(thread_id='retention');id=str(root['id'])
        recorder=DiagnosticArchive()
        event=ComponentEvent(type='trace.span',source='test',run_id=id,payload={'kind':'model','name':'supervisor','status':'completed','duration_ms':5}).model_dump()
        recorder.record(event);self.assertTrue(recorder.flush());recorder.record(event);self.assertTrue(recorder.flush())
        with db_connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) AS n FROM diagnostic_events').fetchone()['n'],1)
            conn.execute("UPDATE diagnostic_events SET timestamp=NOW()-INTERVAL '31 days'")
            conn.execute("UPDATE domain_events SET timestamp=NOW()-INTERVAL '31 days' WHERE root_run_id=%s",(id,))
        self.assertEqual(prune(),1)
        self.assertEqual(read_diagnostics(run_id=id)['events'],[])
        self.assertTrue(read_critical(run_id=id)['events'])

    def test_timestamp_ties_paginate_without_skipping_and_expired_cursor_is_explicit(self):
        recorder=DiagnosticArchive();root=create_run(thread_id='paging');id=str(root['id'])
        timestamp=datetime.now(timezone.utc).isoformat()
        for i in range(5):recorder.record(ComponentEvent(type='run.state',source='test',run_id=id,timestamp=timestamp,payload={'status':'running'}).model_dump())
        self.assertTrue(recorder.flush())
        first=read_diagnostics(run_id=id,limit=2);second=read_diagnostics(run_id=id,limit=2,before=first['next_before']);third=read_diagnostics(run_id=id,limit=2,before=second['next_before'])
        self.assertEqual(len({e['id'] for page in [first,second,third] for e in page['events']}),5)
        with db_connection() as conn:conn.execute('DELETE FROM diagnostic_events WHERE id=%s',(first['next_before'],))
        with self.assertRaises(ValueError):read_diagnostics(run_id=id,before=first['next_before'])

    def test_trace_listing_uses_canonical_state_even_when_diagnostics_are_missing(self):
        from core.execution_traces import read_runs
        root=create_run(thread_id='no-diagnostics');id=str(root['id']);transition_run(id,'running');transition_run(id,'completed',result={'response':'private'})
        trace=read_runs(run_id=id)[0]
        self.assertEqual(trace['status'],'completed');self.assertEqual(trace['events'],[])
        self.assertIn('best-effort',trace['note'])
        self.assertNotIn('private',json.dumps(trace,default=str))
