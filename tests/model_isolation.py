"""Keep model tests independent from the operator's saved choices.

On the server the API container holds data/runtime-settings.json (global model)
and the per-agent assignments. Tests that read the default model would otherwise
see the real selection and fail only on the Debian, never in CI.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class IsolatedModelSettings(unittest.TestCase):
    def setUp(self):
        super().setUp()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        missing = Path(folder.name) / "runtime-settings.json"
        for target in (patch("core.models.RUNTIME_SETTINGS_PATH", missing),
                       patch("core.agent_models.bindings", return_value={})):
            target.start()
            self.addCleanup(target.stop)
