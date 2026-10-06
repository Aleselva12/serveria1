import os
import unittest
from unittest.mock import patch

from core.models import get_model_keep_alive, performance_configuration
from core.runtime import Runtime


class PerformanceConfigurationTests(unittest.TestCase):
    def test_effective_profile_is_non_secret_and_role_aware(self):
        with patch.dict(os.environ, {
            "OLLAMA_MODEL": "base-model",
            "CORA_MODEL_PROGRAMMER": "programmer-model",
            "CORA_MODEL_KEEP_ALIVE": "45m",
            "CORA_CONTEXT_TOKENS": "8192",
            "CORA_OUTPUT_TOKENS": "512",
            "CORA_PERFORMANCE_PROFILE": "pc-test",
            "CORA_PERFORMANCE_HARDWARE_LABEL": "machine-a",
            "CORA_PERFORMANCE_GPU_LABEL": "gpu-a",
        }, clear=False):
            data = performance_configuration("programmer_agent")
        self.assertEqual(get_model_keep_alive(), os.getenv("CORA_MODEL_KEEP_ALIVE", "30m").strip() or "30m")
        self.assertEqual(data["profile"], "pc-test")
        self.assertEqual(data["role"], "programmer")
        self.assertEqual(data["model"], "programmer-model")
        self.assertEqual(data["keep_alive"], "45m")
        self.assertEqual(data["context_tokens"], 8192)
        self.assertEqual(data["output_tokens"], 512)
        self.assertEqual(data["hardware_label"], "machine-a")
        self.assertEqual(data["gpu_label"], "gpu-a")
        self.assertNotIn("password", data)
        self.assertNotIn("token", data)

    def test_runtime_records_profile_and_host_snapshot(self):
        runtime = Runtime(persistent=False)
        with patch.dict(os.environ, {
            "OLLAMA_MODEL": "benchmark-model",
            "CORA_PERFORMANCE_PROFILE": "unit-profile",
        }, clear=False):
            run = runtime.submit("performance-test", lambda current: {"ok": True})
            self.assertTrue(run.done.wait(2))
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.timings["configuration"]["profile"], "unit-profile")
        self.assertEqual(run.timings["configuration"]["model"], "benchmark-model")
        self.assertIn("logical_cpu_count", run.timings["host"])
        self.assertIn("ram_total_gib", run.timings["host"])
        runtime.shutdown()


if __name__ == "__main__":
    unittest.main()
