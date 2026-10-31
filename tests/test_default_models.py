import unittest
from unittest.mock import patch

import core.default_models as default_models


class DefaultModelsTests(unittest.TestCase):
    def setUp(self):
        with default_models._lock:
            default_models._state.update(running=False, current_model=None, completed=[], failed=[], last_error=None)

    def test_status_preserves_extra_installed_models(self):
        installed = [
            {"name": "qwen3:0.6b"},
            {"name": "qwen3:1.7b"},
            {"name": "qwen3:8b"},
            {"name": "nomic-embed-text:latest"},
        ]
        with patch.object(default_models, "list_ollama_models", return_value=installed):
            status = default_models.status()
        self.assertIn("qwen3:4b", status["missing"])
        self.assertNotIn("qwen3:1.7b", [m["name"] for m in status["models"]])
        self.assertEqual(len(default_models.DEFAULT_MODELS), 4)

    def test_start_download_only_pulls_missing_defaults(self):
        installed = [
            {"name": "qwen3:0.6b"},
            {"name": "qwen3:8b"},
            {"name": "nomic-embed-text:latest"},
        ]
        with patch.object(default_models, "list_ollama_models", return_value=installed),              patch.object(default_models.threading, "Thread") as thread:
            status = default_models.start_download()
        self.assertTrue(status["running"])
        args = thread.call_args.kwargs["args"]
        self.assertEqual(args, (["qwen3:4b"],))
        thread.return_value.start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
