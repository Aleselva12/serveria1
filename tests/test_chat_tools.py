import unittest
from types import SimpleNamespace
from unittest.mock import patch
from core.chat_tools import validate_selection, validate_manual_calls


class ChatToolTests(unittest.TestCase):
    def test_model_cannot_call_unselected_tool_in_manual_mode(self):
        validate_manual_calls(None, [{'name':'calendar_create_event'}])
        validate_manual_calls(['calculator_tool'], [{'name':'calculator_tool'}])
        for selection in ([], ['calculator_tool']):
            with self.assertRaises(ValueError): validate_manual_calls(selection, [{'name':'calendar_create_event'}])
    def test_request_selection_distinguishes_auto_none_and_explicit_empty(self):
        tools = [SimpleNamespace(name='calendar_create_event'), SimpleNamespace(name='calculator_tool')]
        self.assertIsNone(validate_selection(None, tools))
        self.assertEqual(validate_selection([], tools), [])
        self.assertEqual(validate_selection(['calendar_create_event'], tools), ['calendar_create_event'])
        for names in (['unknown'], ['calculator_tool','calculator_tool']):
            with self.assertRaises(ValueError): validate_selection(names, tools)

    def test_manual_selection_is_bound_to_model_without_calling_tools_or_approval(self):
        import graph
        with patch('graph.preload_context', return_value=('', [])), patch('graph.with_permanent_context', side_effect=lambda s:s):
            for selection in (['calculator_tool'], []):
                _, _, _, names = graph._runtime_system_prompt([], 'Prepara un preventivo', selection)
                self.assertEqual(names, selection)
        from api import ChatRequest, submit_chat
        from fastapi import HTTPException
        with patch('api.runtime.submit') as submit:
            with self.assertRaises(HTTPException) as error:
                submit_chat(ChatRequest(message='test', manual_tools=['POST /auth/login']))
            self.assertEqual(error.exception.status_code, 422)
            submit.assert_not_called()

    def test_chat_picker_contract_reflects_current_policies_and_does_not_execute(self):
        from core.chat_tools import chat_tool_options
        with patch('core.permissions.policy_overrides', return_value={}):
            options = chat_tool_options()['tools']
        calc = next(t for t in options if t['name'] == 'calculator_tool')
        self.assertTrue(all(p['policy'] == 'auto' for p in calc['permissions']))
        self.assertIn('email_agent_tool', {t['name'] for t in options})
