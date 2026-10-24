import json
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from core.models import get_chat_model, model_options
from core.runtime import Run, current_run, publish_thinking
from core.execution_traces import ExecutionTrace
from core.observability import metadata_event
from deploy import prepare_qwen3

class ModelThinkingTests(unittest.TestCase):
    def test_qwen_profile_overrides_legacy_zero_without_changing_other_families(self):
        for name in ['qwen3:0.6b', 'qwen3:8b']:
            with patch('core.models._default_selection', return_value=(name, 'default')):
                model = get_chat_model('programmer', temperature=0.0)
            self.assertEqual((model.temperature,model.top_p,model.top_k,model.min_p),(.6,.95,20,0))
            self.assertIsNone(model.reasoning)
            request = model._chat_params([])
            self.assertEqual(request["options"]["min_p"], 0)
            self.assertEqual(request["options"]["num_predict"], -1)
            self.assertNotIn("think", request)
            self.assertEqual(model.num_predict,-1)
            self.assertIsNone(model.client_kwargs['timeout'])
        self.assertEqual(model_options('qwen3.5:9b'),{})
        self.assertEqual(model_options('other:8b'),{})

    def test_thinking_only_callback_is_visible_without_becoming_answer(self):
        run=Run('test')
        binding=current_run.set(run)
        try:
            trace=ExecutionTrace('test','test')
            chunk=ChatGenerationChunk(message=AIMessageChunk(content='',additional_kwargs={'reasoning_content':'Leggo i file'}))
            trace.on_llm_new_token('',run_id='span',chunk=chunk)
            self.assertEqual(run.snapshot()['thinking'],'Leggo i file')
            self.assertEqual(run.output,'')
            self.assertIn('first_thinking_ms',run.timings)
            publish_thinking(run,'programmer','span','x'*24001)
            self.assertEqual(len(run.thinking),24000)
            self.assertTrue(run.thinking_truncated)
            publish_thinking(run,'programmer','next','Nuova chiamata')
            self.assertEqual(run.thinking,'Nuova chiamata')
            self.assertFalse(run.thinking_truncated)
        finally:
            current_run.reset(binding)
        self.assertIsNone(metadata_event({'type':'thinking.delta','payload':{'text':'private'}}))

    def test_native_ollama_stream_routes_thinking_through_callback(self):
        from core.models import ConfiguredChatOllama
        from langchain_core.messages import HumanMessage
        run=Run('stream-test')
        binding=current_run.set(run)
        try:
            with patch('core.models._default_selection', return_value=('qwen3:8b', 'default')):
                model=get_chat_model('programmer')
            chunks=[{'message':{'content':'','thinking':'Verifico i file'},'done':False},
                    {'message':{'content':'Risposta'},'done':True,'done_reason':'stop'}]
            with patch.object(ConfiguredChatOllama,'_create_chat_stream',return_value=iter(chunks)), patch('core.execution_traces.append_event'):
                output=list(model.stream([HumanMessage(content='prova')],config={'callbacks':[ExecutionTrace('stream-test','test')]}))
            self.assertEqual(run.thinking,'Verifico i file')
            self.assertEqual(''.join(chunk.content for chunk in output),'Risposta')
        finally:
            current_run.reset(binding)

    def test_preparation_never_selects_model_after_failed_load(self):
        @contextmanager
        def response(path,payload):
            import io
            values={'/api/pull':{'status':'success'}, '/api/show':{'capabilities':['tools','thinking']}, '/api/generate':{'error':'out of memory'}}
            yield io.BytesIO((json.dumps(values[path])+'\n').encode())
        with patch.object(prepare_qwen3.psutil,'virtual_memory',return_value=SimpleNamespace(available=10*1024**3)), patch.object(prepare_qwen3,'post',side_effect=response), patch.object(prepare_qwen3,'save_runtime_model') as save:
            with self.assertRaises(RuntimeError):prepare_qwen3.main()
            save.assert_not_called()

    def test_low_memory_preflight_does_not_download_or_switch(self):
        with patch.object(prepare_qwen3.psutil,'virtual_memory',return_value=SimpleNamespace(available=4*1024**3)), patch.object(prepare_qwen3,'post') as post, patch.object(prepare_qwen3,'save_runtime_model') as save:
            with self.assertRaises(SystemExit):prepare_qwen3.main()
            post.assert_not_called();save.assert_not_called()
