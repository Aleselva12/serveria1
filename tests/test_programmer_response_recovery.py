import unittest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from programmer_agent import programmer_graph as pg
from core.observability import metadata_event


class RecoveryTests(unittest.TestCase):
    def test_repair_after_tools_does_not_replay_tools_or_publish_invalid_calls(self):
        for invalid in (AIMessage(''), AIMessage(' ', invalid_tool_calls=[
            {'name':'programmer_write_file','args':'{','id':'bad','error':'json'}])):
            model = MagicMock(); model.invoke.side_effect = [invalid, AIMessage('Ho letto, nessuna modifica.')]
            state = {'system_prompt':'identity', 'messages':[HumanMessage('Crea'),
                AIMessage('', tool_calls=[{'name':'programmer_search_code','args':{},'id':'a','type':'tool_call'}]),
                ToolMessage('found', name='programmer_search_code', tool_call_id='a')]}
            with patch.object(pg, 'programmer_model', return_value=model), patch.object(pg, 'record_metric'), \
                 patch.object(pg._tool_node, 'invoke') as execute:
                result = pg.call_llm(state)
            execute.assert_not_called()
            self.assertEqual(model.invoke.call_count, 2)
            self.assertEqual(result['messages'][0].content, 'Ho letto, nessuna modifica.')
            self.assertNotIn(invalid, model.invoke.call_args.args[0])
            self.assertEqual(len(state['messages']), 3)

    def test_repeated_empty_is_typed_failure_and_diagnostics_contain_no_content(self):
        model = MagicMock(); model.invoke.return_value = AIMessage('', additional_kwargs={'reasoning_content':'private'})
        with patch.object(pg, 'programmer_model', return_value=model), patch.object(pg, 'record_metric') as metric:
            with self.assertRaises(pg.ProgrammerResponseError):
                pg.call_llm({'system_prompt':'identity','messages':[HumanMessage('create')]})
        validation = [args.args[1] for args in metric.call_args_list if args.args[0] == 'response_validation']
        self.assertEqual([r['reason'] for r in validation], ['empty_response']*2)
        event = metadata_event({'type':'programmer.response_validation','payload':{**validation[0], 'content':'private'}})
        self.assertNotIn('content', event['payload'])

    def test_whitespace_and_thinking_blocks_are_not_text_answers(self):
        for content in (' ', [{'type':'reasoning','reasoning':'private'}]):
            self.assertEqual(pg.response_problem(AIMessage(content)), 'empty_response')
        self.assertIsNone(pg.response_problem(AIMessage([{'type':'text','text':'answer'}])))

    def test_evidence_only_includes_tool_results_from_current_user_turn(self):
        messages = [HumanMessage('old'), ToolMessage('old result',name='old_write',tool_call_id='a'),
                    HumanMessage('new'), ToolMessage('read result',name='read_file',tool_call_id='b'), AIMessage('Creato')]
        with patch.object(pg.ws,'current',return_value='workspace'), patch('programmer_agent.components.check_history',return_value=[]), \
             patch.object(pg,'record_metric'):
            content = pg.final_evidence({'messages':messages})['messages'][0].content
        self.assertIn('read_file', content); self.assertNotIn('old_write', content)
        self.assertIn('Risultato non verificato', content)
