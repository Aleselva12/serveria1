import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from core import agent_models as assignments, models


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'runtime-settings.json'
        self.settings = patch.object(models, 'RUNTIME_SETTINGS_PATH', self.path)
        self.settings.start()

    def tearDown(self):
        self.settings.stop(); self.tmp.cleanup()

    def test_per_agent_persistence_override_reset_and_other_roles(self):
        with patch.object(models, 'list_ollama_models', return_value=[{'name': 'base'}, {'name': 'code'}]):
            models.save_runtime_model('base')
            assignments.save_binding('programmer_agent', 'local', 'code')
            self.assertEqual(models.get_model_name('programmer'), 'code')
            self.assertEqual(models.get_model_name('supervisor'), 'base')
            self.assertEqual(json.loads(assignments.path().read_text())['programmer']['model'], 'code')
            models.save_runtime_model('base')
            self.assertEqual(models.get_model_name('programmer'), 'code')
            assignments.save_binding('programmer_agent', 'inherit', '')
            self.assertEqual(models.get_model_name('programmer'), 'base')

    def test_failed_atomic_write_keeps_old_binding(self):
        with patch.object(models, 'list_ollama_models', return_value=[{'name': 'first'}, {'name': 'second'}]):
            assignments.save_binding('audio_agent', 'local', 'first')
            with patch.object(assignments.os, 'replace', side_effect=OSError('disk')):
                with self.assertRaises(OSError): assignments.save_binding('audio_agent', 'local', 'second')
            self.assertEqual(models.get_model_name('audio'), 'first')

    def test_invalid_agent_missing_local_model_and_corrupt_file_fail_closed(self):
        with self.assertRaises(HTTPException): assignments.save_binding('fake', 'inherit', '')
        with patch.object(models, 'list_ollama_models', return_value=[]):
            with self.assertRaises(HTTPException): assignments.save_binding('audio_agent', 'local', 'missing')
        assignments.path().write_text('broken')
        with self.assertRaises(RuntimeError): models.get_model_name('audio')

    def test_remote_off_profile_mismatch_and_old_bridge_are_rejected_without_fallback(self):
        row = {'id': 'pc', 'enabled': False, 'active_profile': 'light', 'profiles': {'heavy': 'big', 'medium': 'mid', 'light': 'small'}}
        with patch.dict(os.environ, {'CORA_RUNTIME_MODE': 'server'}), patch('core.machines_api._find', return_value=row), patch('core.machines_api._worker_call') as call:
            with self.assertRaises(HTTPException): assignments.chat_on_worker('pc', 'small', {})
            call.assert_not_called()
            row['enabled'] = True
            with self.assertRaises(HTTPException): assignments.chat_on_worker('pc', 'big', {})
            call.assert_not_called()
            call.return_value = {'models': [{'name': 'small'}]}
            with self.assertRaises(HTTPException): assignments.save_binding('audio_agent', 'pc', 'small')
            call.return_value = {'models': [{'name': 'small'}], 'agent_chat': True}
            assignments.save_binding('audio_agent', 'pc', 'small')
            row['enabled'] = False
            with self.assertRaises(HTTPException): models.get_chat_model('audio').invoke([HumanMessage(content='test')])
        self.assertEqual(models.get_model_name('audio'), 'small')

    def test_single_manual_selection_prevents_unapproved_agent_switch(self):
        row = {"id": "pc", "enabled": True, "selected_model": "qwen3-coder:30b-a3b-q4_K_M",
               "active_profile": "light",
               "profiles": {"heavy": "old-heavy", "medium": "old-medium", "light": "old-light"}}
        with patch.dict(os.environ, {"CORA_RUNTIME_MODE": "server"}), \
             patch("core.machines_api._find", return_value=row), \
             patch("core.machines_api._worker_call") as remote:
            assignments.remote_machine("pc", "qwen3-coder:30b-a3b-q4_K_M")
            with self.assertRaises(HTTPException) as denied:
                assignments.remote_machine("pc", "old-light")
            self.assertEqual(denied.exception.status_code, 409)
            remote.assert_not_called()

    def test_remote_chat_preserves_native_tools_and_async_messages(self):
        @tool
        def note(content: str) -> str:
            """Append a note."""
            return content
        reply = {'model': 'remote', 'message': {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': 'note', 'arguments': {'content': '{"keep":"text"}'}}}]}, 'done': True}
        with patch.object(assignments, 'binding', return_value={'machine_id': 'pc', 'model': 'remote'}), patch.object(assignments, 'chat_on_worker', return_value=reply) as remote:
            chat = models.get_chat_model('audio').bind_tools([note])
            response = chat.invoke([HumanMessage(content='append')])
            self.assertEqual(response.tool_calls[0]['args']['content'], '{"keep":"text"}')
            self.assertEqual(remote.call_args.args[2]['tools'][0]['function']['name'], 'note')
            # Run the returned tool locally, then send its result back through the remote chat.
            result_message = note.invoke(response.tool_calls[0])
            remote.return_value = {'model': 'remote', 'message': {'role': 'assistant', 'content': 'done'}, 'done': True}
            final = chat.invoke([HumanMessage(content='append'), response, result_message])
            self.assertEqual(final.content, 'done')
            self.assertEqual(remote.call_args.args[2]['messages'][-1]['role'], 'tool')
            remote.return_value = reply
            result = asyncio.run(chat.ainvoke([HumanMessage(content='append')]))
            self.assertEqual(result.tool_calls[0]['name'], 'note')

    def test_remote_dispatch_checks_profile_every_request_and_keeps_settings(self):
        row = {'id': 'pc', 'enabled': True, 'active_profile': 'light', 'profiles': {'heavy': 'big', 'medium': 'mid', 'light': 'small'}}
        before = json.dumps(row, sort_keys=True)
        with patch.dict(os.environ, {'CORA_RUNTIME_MODE': 'server'}), patch('core.machines_api._find', return_value=row), patch('core.machines_api._worker_call', return_value={'ok': True}) as call:
            assignments.chat_on_worker('pc', 'small', {'messages': [{'role': 'user', 'content': 'hello'}], 'tools': [], 'model': 'small'})
            self.assertEqual(call.call_args.args[1], '/chat')
            self.assertFalse(call.call_args.args[2]['stream'])
            self.assertEqual(json.dumps(row, sort_keys=True), before)
        with patch.dict(os.environ, {'CORA_RUNTIME_MODE': 'isolated'}):
            with self.assertRaises(HTTPException): assignments.remote_machine('pc', 'small')
