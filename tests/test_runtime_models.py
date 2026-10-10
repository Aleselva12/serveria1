"""Model changes must reach already-imported agents without restarting Cora."""
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core import models


class RuntimeModelTests(unittest.TestCase):
    def test_selection_persists_and_overrides_every_role(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            with patch.object(models, 'RUNTIME_SETTINGS_PATH', path), patch.object(models, 'list_ollama_models', return_value=[{'name': 'new'}]), patch.dict(os.environ, {'CORA_MODEL_RESEARCH': 'old'}):
                models.save_runtime_model('new')
                self.assertEqual(json.loads(path.read_text()), {'model': 'new'})
                for role in models.ROLE_MODEL_ENV:
                    self.assertEqual(models.get_chat_model(role).model, 'new')
                with self.assertRaises(ValueError):
                    models.save_runtime_model('not-installed')
                self.assertEqual(models.get_model_name('research'), 'new')

    def test_failed_atomic_publish_preserves_previous_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            path.write_text('{"model":"old"}')
            with patch.object(models, 'RUNTIME_SETTINGS_PATH', path), patch.object(models, 'list_ollama_models', return_value=[{'name': 'new'}]), patch.object(models.os, 'replace', side_effect=OSError('disk')):
                with self.assertRaises(OSError): models.save_runtime_model('new')
                self.assertEqual(models.get_model_name(), 'old')
                self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_non_object_settings_use_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            path.write_text('[]')
            with patch.object(models, 'RUNTIME_SETTINGS_PATH', path), patch.dict(os.environ, {'CORA_MODEL_RESEARCH': 'role-model'}):
                self.assertEqual(models.get_model_name('research'), 'role-model')

    def test_imported_specialists_resolve_current_model_on_each_call(self):
        modules = [('search_agent.search_graph', 'research'), ('email_agent.email_graph', 'email'), ('audio_agent.audio_graph', 'audio'), ('structure_agent.structure_graph', 'structure'), ('programmer_agent.programmer_graph', 'programmer')]
        for name, role in modules:
            with self.subTest(agent=name):
                module = importlib.import_module(name)
                first, second = MagicMock(), MagicMock()
                first.bind_tools.return_value = first
                second.bind_tools.return_value = second
                with patch.object(module, 'get_chat_model', side_effect=[first, second]) as factory, patch.object(module, 'fit_messages', return_value=[]), patch.object(module, 'ensure_runtime_active'):
                    module.call_llm({'system_prompt': 'test', 'messages': []})
                    module.call_llm({'system_prompt': 'test', 'messages': []})
                self.assertEqual(factory.call_count, 2)
                factory.assert_called_with(role, temperature=0.0)
                first.invoke.assert_called_once()
                second.invoke.assert_called_once()
