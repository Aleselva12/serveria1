import os
import unittest
from unittest.mock import patch
from core.generation_policy import run_timeout, model_timeout, output_tokens, response_instruction
from core.models import get_chat_model, performance_configuration
from core.context_budget import fit_messages
from langchain_core.messages import HumanMessage

class GenerationPolicyTests(unittest.TestCase):
    def test_unlimited_overrides_installed_legacy_budgets(self):
        with patch.dict(os.environ, {'CORA_UNLIMITED_GENERATION':'true', 'CORA_RUN_TIMEOUT_SECONDS':'300', 'CORA_MODEL_TIMEOUT_SECONDS':'180', 'CORA_OUTPUT_TOKENS':'512'}):
            self.assertEqual(run_timeout(), 0)
            self.assertIsNone(model_timeout())
            model = get_chat_model('programmer')
            self.assertEqual(model.num_predict, -1)
            self.assertIsNone(model.client_kwargs['timeout'])
            self.assertEqual(performance_configuration('programmer_agent')['output_tokens'], -1)

    def test_explicit_bounded_mode_and_zero_timeout(self):
        with patch.dict(os.environ, {'CORA_UNLIMITED_GENERATION':'false', 'CORA_RUN_TIMEOUT_SECONDS':'300', 'CORA_MODEL_TIMEOUT_SECONDS':'180', 'CORA_OUTPUT_TOKENS':'512'}):
            self.assertEqual((run_timeout(), model_timeout(), output_tokens()), (300,180,512))
        with patch.dict(os.environ, {'CORA_UNLIMITED_GENERATION':'false', 'CORA_MODEL_TIMEOUT_SECONDS':'0'}):
            self.assertIsNone(model_timeout())

    def test_unlimited_generation_keeps_positive_context_reserve(self):
        with patch.dict(os.environ, {'CORA_UNLIMITED_GENERATION':'true', 'CORA_CONTEXT_TOKENS':'8192'}):
            # Unlimited output must budget the same input as a finite context reserve.
            messages = [HumanMessage(content='ciao')]
            self.assertEqual(fit_messages(messages, reserve=256), fit_messages(messages, reserve=256, output_reserve=1024))

    def test_style_never_requests_incomplete_work(self):
        for length in ['short','medium','long']:
            self.assertIn('Completa sempre il compito', response_instruction(length))
