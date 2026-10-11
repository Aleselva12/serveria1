import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
import httpx
from ollama import ResponseError
from core.provider_errors import provider_detail, MESSAGES
from core import execution_traces as traces
from core.observability import DiagnosticArchive, metadata_event
from core.event_bus import EventBus


class ProviderErrorTests(unittest.TestCase):
    def test_provider_classification_never_copies_private_text(self):
        cases=[(ResponseError('model secret not found',404),'missing'),
               (ResponseError('secret out of memory',500),'memory'),
               (ResponseError('secret does not support tools',400),'tools'),
               (httpx.ConnectError('https://secret'),'connection'),
               (httpx.ReadTimeout('secret'),'timeout')]
        for error,category in cases:
            self.assertEqual(provider_detail(error),MESSAGES[category])
            self.assertNotIn('secret',provider_detail(error))
        self.assertIsNone(provider_detail(ValueError('secret')))

    def test_arbitrary_detail_and_tool_errors_are_rejected_at_archive_boundary(self):
        for kind,detail in [('model','secret'),('tool',MESSAGES['memory'])]:
            row=metadata_event({'type':'trace.span','payload':{'kind':kind,'error_detail':detail}})
            self.assertIsNone(row['payload']['error_detail'])

    def test_callback_bus_archive_and_jsonl_keep_only_safe_model_detail(self):
        bus=EventBus();archive=DiagnosticArchive()
        with tempfile.TemporaryDirectory() as tmp, patch('core.event_bus.bus',bus), patch('core.observability.archive',archive), patch.object(traces,'TRACE_FILE',Path(tmp)/'trace.jsonl'), patch.dict('os.environ',{'CORA_DIAGNOSTIC_JSONL_EXPORT':'true'}):
            trace=traces.ExecutionTrace('thread','v1');span=uuid4()
            trace.on_chat_model_start({},[],run_id=span)
            trace.on_llm_error(ResponseError('secret not found',404),run_id=span)
            live=bus.read()[0];saved=list(archive.queue)
            self.assertEqual(live[-1]['payload']['error_detail'],MESSAGES['missing'])
            self.assertEqual(saved[-1]['payload']['error_detail'],MESSAGES['missing'])
            self.assertNotIn('secret',json.dumps(saved))
            self.assertNotIn('secret',traces.TRACE_FILE.read_text())
            span=uuid4();trace.on_tool_start({'name':'test'},'secret',run_id=span)
            trace.on_tool_error(ValueError('secret'),run_id=span)
            self.assertIsNone(bus.read()[0][-1]['payload']['error_detail'])

    def test_persisted_diagnostic_projection_reaches_run_view(self):
        identifier=str(uuid4())
        row={'id':identifier,'parent_run_id':None,'metadata':{},'created_at':'2026-10-11'}
        snapshot={'id':identifier,'thread_id':'thread','status':'failed','elapsed_ms':1,'timings':{}}
        event=metadata_event({'type':'trace.span','timestamp':'2026-10-11','payload':{'kind':'model','status':'error','error_type':'ResponseError','error_detail':MESSAGES['memory']}})
        with patch.object(traces,'database_configured',return_value=True), patch('core.run_lifecycle.get_run',return_value=row), patch('core.run_lifecycle.persisted_snapshot',return_value=snapshot), patch('core.observability.read',return_value={'events':[event],'truncated':False}):
            result=traces.read_runs(run_id=identifier)
        self.assertEqual(result[0]['events'][0]['error_detail'],MESSAGES['memory'])

    def test_safe_detail_is_in_sql_insert_payload(self):
        from unittest.mock import MagicMock
        from core.protocol import ComponentEvent
        archive=DiagnosticArchive()
        event=ComponentEvent(type='trace.span',source='tracing',payload={'kind':'model','error_detail':MESSAGES['timeout'],'prompt':'secret'})
        archive.record(event.model_dump(mode='json'))
        connection=MagicMock()
        with patch('core.observability.database_configured',return_value=True), patch('core.observability.db_connection',return_value=connection):
            self.assertTrue(archive.flush())
        inserted=connection.__enter__.return_value.execute.call_args.args[1][-1].obj
        self.assertEqual(inserted['payload']['error_detail'],MESSAGES['timeout'])
        self.assertNotIn('secret',json.dumps(inserted))
        self.assertEqual(archive.persisted,1)

    def test_old_jsonl_private_details_are_not_exposed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(traces,'TRACE_FILE',Path(tmp)/'trace.jsonl'), patch.object(traces,'database_configured',return_value=False), patch.dict('os.environ',{'CORA_DIAGNOSTIC_JSONL_EXPORT':'true'}):
            traces.TRACE_FILE.write_text(json.dumps({'run_id':'id','thread_id':'t','kind':'model','status':'error','timestamp':'now','duration_ms':0,'graph_version':'v1','error_detail':'secret'})+'\n')
            self.assertNotIn('secret',json.dumps(traces.read_runs()))
