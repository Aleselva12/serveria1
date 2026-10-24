"""Router contract/integration tests; semantic accuracy needs a live local model."""
import os
import unittest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from programmer_agent import request_router as router, context_manager as cm, programmer_graph as pg
from programmer_agent.programmer_tools import PROGRAMMER_TOOLS


def decision(**changes):
    route = dict(intent='conversation', context=['current'], tool_groups=[], difficulty=1, confidence=0.95)
    route.update(changes)
    return {'status': 'classified', 'route': route}


class RouterTests(unittest.TestCase):
    def model(self, route=None):
        import json
        model = MagicMock()
        model.model = "qwen3:8b"
        model.model_copy.return_value = model
        model.invoke.return_value = AIMessage(json.dumps((route or decision())['route']))
        return model

    def test_semantic_input_is_not_limited_to_programming_languages(self):
        for task in ['Preferisci Python o C++?', 'Preferisci scrivere in italiano o inglese?',
                     'Do you enjoy explaining science?', 'Spiega il paradosso del mentitore']:
            model = self.model()
            with patch.object(router, 'get_chat_model', return_value=model):
                result = router.classify([HumanMessage(task)])
            self.assertEqual(result['status'], 'classified')
            self.assertIn(task, model.invoke.call_args.args[0][-1].content)
            self.assertIn('duration_ms', result)
            tools, reason = cm.semantic_tools([HumanMessage(task)], PROGRAMMER_TOOLS, result)
            self.assertEqual([t.name for t in tools], ['programmer_catalog'])

    def test_recent_history_and_dependent_context_are_preserved(self):
        messages = [HumanMessage('Chiamiamolo Cora'), AIMessage('Va bene'), HumanMessage('Come abbiamo deciso di chiamarlo?')]
        model = self.model(decision(context=['current', 'history']))
        with patch.object(router, 'get_chat_model', return_value=model):
            result = router.classify(messages)
        self.assertIn('Chiamiamolo Cora', model.invoke.call_args.args[0][-1].content)
        fitted, tools, reason = cm.prepare('full', messages, PROGRAMMER_TOOLS, result, 'small')
        self.assertEqual(fitted[1:], messages)
        self.assertTrue(fitted[0].content.startswith('full'))
        self.assertTrue(cm.ESSENTIAL <= {t.name for t in tools})

    def test_easy_file_action_still_has_edit_tools(self):
        messages = [HumanMessage('Rinomina questa cartella')]
        result = decision(intent='modification', context=['current', 'files'], tool_groups=['edit'])
        tools, _ = cm.semantic_tools(messages, PROGRAMMER_TOOLS, result)
        self.assertIn('programmer_write_file', {t.name for t in tools})
        self.assertTrue(cm.ESSENTIAL <= {t.name for t in tools})

    def test_only_standalone_metadata_can_be_omitted(self):
        for messages in ([HumanMessage('Ciao')], [HumanMessage('prima'), AIMessage('ok'), HumanMessage('Ciao')]):
            fitted, _, _ = cm.prepare('workspace policies', messages, PROGRAMMER_TOOLS, decision(), 'policies')
            self.assertTrue(fitted[0].content.startswith('policies' if len(messages) == 1 else 'workspace policies'))
            self.assertEqual(fitted[1:], messages)

    def test_catalog_escalates_and_preserves_exchange(self):
        messages = [HumanMessage('Ciao'), AIMessage('', tool_calls=[{'name':'programmer_catalog', 'args':{}, 'id':'a'}]),
                    ToolMessage('{}', tool_call_id='a')]
        fitted, tools, reason = cm.prepare('full', messages, PROGRAMMER_TOOLS, decision(), 'small')
        self.assertEqual(tools, PROGRAMMER_TOOLS)
        self.assertEqual(reason, 'expanded_after_discovery_or_error')
        self.assertEqual(fitted[1:], messages)
        self.assertTrue(fitted[0].content.startswith('full'))

    def test_errors_uncertainty_and_bad_schema_fall_back(self):
        for reply in [AIMessage('not json'), AIMessage('{"intent":"conversation"}'), TimeoutError('offline')]:
            model = self.model()
            if isinstance(reply, Exception): model.invoke.side_effect = reply
            else: model.invoke.return_value = reply
            with patch.object(router, 'get_chat_model', return_value=model):
                result = router.classify([HumanMessage('ciao')])
            self.assertEqual(result['status'], 'router_error')
            self.assertEqual(cm.semantic_tools([HumanMessage('ciao')], PROGRAMMER_TOOLS, result)[0], PROGRAMMER_TOOLS)
        for route in [decision(confidence=0.4), decision(intent='unknown'), decision(context=['files']), decision(difficulty=11)]:
            self.assertEqual(cm.semantic_tools([HumanMessage('ciao')], PROGRAMMER_TOOLS, route)[0], PROGRAMMER_TOOLS)

    def test_unsupported_inputs_and_disabled_router_do_not_invoke(self):
        cases = [[HumanMessage('x'*7000)], [HumanMessage(content=[{'type':'text','text':'ciao'}])],
                 [HumanMessage('read'), ToolMessage('data', tool_call_id='a'), HumanMessage('poi?')]]
        with patch.object(router, 'get_chat_model') as factory:
            for messages in cases:
                self.assertIsNone(router.classify(messages)['route'])
            with patch.dict(os.environ, {'CORA_CONTEXT_ROUTER_MODE':'off'}):
                self.assertEqual(router.classify([HumanMessage('ciao')])['status'], 'disabled')
            factory.assert_not_called()

    def test_cancellation_is_not_swallowed(self):
        from core.run_lifecycle import RunCancelled
        from core.runtime_context import RunTimedOut
        for error in [RunCancelled('stop'), RunTimedOut('deadline')]:
            model = self.model()
            model.invoke.side_effect = error
            with patch.object(router, 'get_chat_model', return_value=model):
                with self.assertRaises(type(error)): router.classify([HumanMessage('ciao')])

    def test_graph_classifies_once_and_reuses_route_across_calls(self):
        messages = [HumanMessage('Italiano o inglese?')]
        model = MagicMock()
        model.invoke.return_value = AIMessage('Italiano')
        with patch.dict(os.environ, {'CORA_CONTEXT_MANAGER_ENABLED':'true'}), \
             patch.object(router, 'classify', return_value=decision()) as classify, \
             patch.object(pg, 'with_permanent_context', side_effect=lambda s:s), \
             patch.object(pg.ws, 'current', return_value='test'), \
             patch.object(pg.ws, 'manifest', return_value={}), \
             patch.object(pg.ws, 'summary', return_value={}), \
             patch.object(pg, 'programmer_model', return_value=model), \
             patch.object(pg, 'record_metric'):
            state = {'messages': messages}
            state.update(pg.prepare_prompt(state))
            self.assertIn("Workspace ID: test", state["conversation_prompt"])
            pg.call_llm(state)
            pg.call_llm(state)
            classify.assert_called_once()
        self.assertEqual(model.invoke.call_count, 2)

    def test_local_model_request_is_bounded_and_uses_operator_model(self):
        from core.models import get_chat_model
        for name, expected in [('qwen3:8b', False), ('gpt-oss:20b', 'low')]:
            with patch('core.models._default_selection', return_value=(name, 'default')):
                model = get_chat_model('programmer', format=router.Route.model_json_schema(),
                                       num_predict=256, client_kwargs={'timeout':5, 'trust_env':False})
            reply = self.model().invoke.return_value
            with patch.object(router, 'get_chat_model', return_value=model), \
                 patch.object(type(model), 'invoke', return_value=reply) as invoke:
                result = router.classify([HumanMessage('Italiano o inglese?')])
            self.assertEqual(result['status'], 'classified')
            self.assertEqual(result['model'], name)
            self.assertFalse(invoke.call_args.kwargs['stream'])
            params = model.model_copy(update={'reasoning':expected})._chat_params([HumanMessage('test')], stream=False)
            self.assertEqual(params['options']['num_predict'], 256)
            self.assertEqual(params['think'], expected)
            self.assertEqual(params['model'], name)

    def test_disabled_manager_never_classifies(self):
        with patch.dict(os.environ, {'CORA_CONTEXT_MANAGER_ENABLED':'false'}), \
             patch.object(router, 'classify') as classify, \
             patch.object(pg, 'with_permanent_context', side_effect=lambda s:s), \
             patch.object(pg.ws, 'current', return_value='test'), \
             patch.object(pg.ws, 'manifest', return_value={}), \
             patch.object(pg.ws, 'summary', return_value={}):
            pg.prepare_prompt({'messages':[HumanMessage('ciao')]})
            classify.assert_not_called()
