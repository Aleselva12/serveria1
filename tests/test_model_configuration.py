import importlib
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
from contextlib import ExitStack
from langchain_core.messages import HumanMessage
from core import models, agent_models, model_evidence


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.object(models, 'RUNTIME_SETTINGS_PATH', Path(self.temp.name) / 'runtime-settings.json')
        self.settings.start()

    def tearDown(self):
        self.settings.stop(); self.temp.cleanup()

    def test_factory_resolves_machine_and_model_from_one_binding_read(self):
        with patch.object(agent_models, 'binding', side_effect=[{'model': 'remote', 'machine_id': 'pc'}, {'model': 'local', 'machine_id': 'local'}]) as read:
            model = models.get_chat_model('audio')
        self.assertEqual((model.model, model.remote_machine_id), ('remote', 'pc'))
        read.assert_called_once_with('audio')

    def test_provider_evidence_is_not_configuration_or_generated_text(self):
        native = {'model': 'actual-model', 'message': {'role': 'assistant', 'content': 'PRIVATE_OUTPUT'}, 'done': True}
        with patch.object(models, '_default_selection', return_value=('requested', 'default')), patch('langchain_ollama.ChatOllama._create_chat_stream', return_value=iter([native])):
            reply = models.get_chat_model('audio').invoke([HumanMessage(content='PRIVATE_INPUT')])
        evidence = model_evidence.observations()['audio']
        self.assertEqual(evidence['reported_model'], 'actual-model')
        self.assertFalse(evidence['matches_requested'])
        self.assertEqual(reply.content, 'PRIVATE_OUTPUT')
        raw = model_evidence._path().read_text()
        self.assertNotIn('PRIVATE_INPUT', raw); self.assertNotIn('PRIVATE_OUTPUT', raw)
        with patch.object(models, 'list_ollama_models', return_value=[{'name': 'different'}]):
            agent_models.save_binding('audio_agent', 'local', 'different')
        self.assertNotEqual(models.resolve_model('audio')['configuration_id'], evidence['configuration_id'])

    def test_missing_model_metadata_cannot_confirm_a_model(self):
        row = model_evidence.observe('audio', 'expected', 'local', 'v1', {'done': True, 'message': {'content': 'OK'}})
        self.assertIsNone(row['reported_model']); self.assertIsNone(row['matches_requested'])
        self.assertTrue(model_evidence.matches_requested('qwen3', 'qwen3:latest'))
        self.assertIsNone(model_evidence.observe('audio', 'x', 'local', 'v1', {'done': False, 'model': 'x'}))

    def test_real_agent_nodes_pick_up_saved_models_without_reimport_or_restart(self):
        definitions = [('graph', 'call_model', 'supervisor', 'supervisor'),
            ('structure_agent.structure_graph', 'call_llm', 'structure', 'structure_agent'),
            ('search_agent.search_graph', 'call_llm', 'research', 'local_research_agent'),
            ('audio_agent.audio_graph', 'call_llm', 'audio', 'audio_agent'),
            ('email_agent.email_graph', 'call_llm', 'email', 'email_quotes_agent'),
            ('programmer_agent.programmer_graph', 'call_llm', 'programmer', 'programmer_agent')]
        captured = []
        def reply(model, *args, **kwargs):
            captured.append((model.cora_role, model.model, model.remote_machine_id))
            yield {'model': model.model, 'message': {'role': 'assistant', 'content': 'OK'}, 'done': True}
        available = [{'name': 'base'}] + [{'name': role + '-changed'} for _, _, role, _ in definitions]
        with patch.object(models, 'list_ollama_models', return_value=available):
            models.save_runtime_model('base')
            for name, function, role, identifier in definitions:
                module = importlib.import_module(name)
                with ExitStack() as stack:
                    stack.enter_context(patch.object(module, 'ensure_runtime_active'))
                    fit = 'fit_programmer_messages' if role == 'programmer' else 'fit_messages'
                    stack.enter_context(patch.object(module, fit, return_value=[HumanMessage(content='test')]))
                    stack.enter_context(patch.object(models.ConfiguredChatOllama, '_create_chat_stream', autospec=True, side_effect=reply))
                    getattr(module, function)({'system_prompt': 'test', 'messages': []})
                    self.assertEqual(captured[-1], (role, 'base', None))
                    agent_models.save_binding(identifier, 'local', role + '-changed')
                    getattr(module, function)({'system_prompt': 'test', 'messages': []})
                    self.assertEqual(captured[-1], (role, role + '-changed', None))
            self.assertEqual(len(captured), 12)

    def test_specialist_change_does_not_change_the_main_chat(self):
        with patch.object(models, 'list_ollama_models', return_value=[{'name': 'base'}, {'name': 'audio-new'}]):
            models.save_runtime_model('base')
            agent_models.save_binding('audio_agent', 'local', 'audio-new')
        self.assertEqual(models.get_chat_model('supervisor').model, 'base')
        self.assertEqual(models.get_chat_model('audio').model, 'audio-new')

    def test_verification_uses_saved_factory_no_tools_and_rejects_queued_changes(self):
        from core.architecture_api import verify_agent_model
        jobs = []
        def submit(thread, work, **kwargs): jobs.append(work); return SimpleNamespace(id='test-run')
        with patch('core.runtime.runtime.submit', side_effect=submit), patch('core.runtime.checkpoint'):
            result = verify_agent_model('audio_agent')
            self.assertEqual(result['run_id'], 'test-run')
            with patch('core.agent_models.binding', return_value={'model': 'changed', 'machine_id': 'local'}):
                with self.assertRaisesRegex(RuntimeError, 'Configurazione cambiata'): jobs[0](None)
            response = {'model': models.get_model_name('audio'), 'message': {'role': 'assistant', 'content': 'OK'}, 'done': True}
            with patch('langchain_ollama.ChatOllama._create_chat_stream', return_value=iter([response])):
                report = jobs[0](None)
            self.assertTrue(report['provider_reported']); self.assertTrue(report['matches_requested'])
            self.assertFalse(report['tools_executed'])
            no_model = {'message': {'role': 'assistant', 'content': 'OK'}, 'done': True}
            with patch('langchain_ollama.ChatOllama._create_chat_stream', return_value=iter([no_model])):
                unconfirmed = jobs[0](None)
            self.assertFalse(unconfirmed['provider_reported'])
            self.assertIsNone(unconfirmed['reported_model'])

    def test_whisper_configuration_and_reload_are_separate_from_llm(self):
        from audio_agent import audio_tools
        from core.audio_api import reload_transcription_engine
        from fastapi import HTTPException
        audio_tools._load_whisper_model.cache_clear()
        factory = Mock()
        try:
            with patch.dict(os.environ, {'CORA_WHISPER_MODEL': 'small', 'CORA_WHISPER_LOCAL_ONLY': 'false'}), patch.dict('sys.modules', {'faster_whisper': SimpleNamespace(WhisperModel=factory)}):
                audio_tools._load_whisper_model()
                self.assertEqual(audio_tools.transcription_configuration()['loaded']['model'], 'small')
                with patch.dict(os.environ, {'CORA_WHISPER_MODEL': 'medium'}):
                    self.assertEqual(audio_tools.transcription_configuration()['model'], 'medium')
                    self.assertEqual(audio_tools.transcription_configuration()['loaded']['model'], 'small')
                    slot = threading.Lock()
                    with patch('core.audio_api.runtime.slot', slot):
                        slot.acquire()
                        with self.assertRaises(HTTPException): reload_transcription_engine()
                        slot.release()
                        self.assertTrue(reload_transcription_engine()['reloaded'])
                    self.assertIsNone(audio_tools.transcription_configuration()['loaded'])
                    audio_tools._load_whisper_model()
                    self.assertEqual(audio_tools.transcription_configuration()['loaded']['model'], 'medium')
                    self.assertEqual(factory.call_count, 2)
        finally: audio_tools._load_whisper_model.cache_clear()

    def test_chat_message_uses_observed_reply_not_current_supervisor_setting(self):
        import api
        from contextlib import nullcontext
        from langchain_core.messages import AIMessage
        from uuid import uuid4
        for observed in [[], [{'role': 'research', 'reported_model': 'document-model', 'machine_id': 'pc'}]]:
            with self.subTest(observed=bool(observed)):
                run = SimpleNamespace(thread_id=str(uuid4()), id=str(uuid4()), timings={'inference_observations': observed}, graph_version='v1')
                with ExitStack() as stack:
                    stack.enter_context(patch.object(api, 'ensure_conversation'))
                    stack.enter_context(patch.object(api, 'request_content', return_value='test'))
                    save = stack.enter_context(patch.object(api, 'save_message', side_effect=[{'id': uuid4()}, {'id': uuid4()}]))
                    stack.enter_context(patch.object(api, 'set_working_memory'))
                    stack.enter_context(patch.object(api, 'logged_operation', return_value=nullcontext({})))
                    stack.enter_context(patch.object(api, 'ExecutionTrace'))
                    stack.enter_context(patch.object(api, 'prepare_context', return_value=[]))
                    stack.enter_context(patch.object(api, 'checkpoint'))
                    stack.enter_context(patch.object(api, 'get_model_name', return_value='unrelated-new-selection'))
                    stack.enter_context(patch.object(api.graph, 'stream', return_value=iter([('values', {'messages': [AIMessage(content='answer')]})])))
                    stack.enter_context(patch.object(api.postprocess, 'submit'))
                    api.execute_chat(api.ChatRequest(message='test'), run)
                saved = save.call_args.kwargs
                self.assertEqual(saved['model_id'], 'document-model' if observed else None)
                self.assertEqual(saved['metadata']['inference_observations'], observed)
