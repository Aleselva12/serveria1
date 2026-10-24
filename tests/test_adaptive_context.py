"""Reproduce a successful large Library read followed by a model turn."""
import os
import unittest
from unittest.mock import patch
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from core.context_budget import fit_messages, _valid_exchange, message_cost

class AdaptiveContextTests(unittest.TestCase):
    def test_large_library_read_keeps_customer_near_end_and_complete_tool_exchange(self):
        content = 'SOURCE_PATH: clienti/test.docx\n--- DOCUMENT CONTENT ---\n' + ('Other customer\n' * 7000) + '\nCAPITAN VENTURA\n24/10/2026\nUltimo accordo: richiamare lunedi\n' + ('Other customer\n' * 1000)
        messages = [SystemMessage('Use only sources. Disclose partial excerpts.'),
                    HumanMessage('Leggi le ultime note di Capitan Ventura'),
                    AIMessage('', tool_calls=[{'id':'read-1','name':'library_read','args':{'relative_path':'clienti/test.docx'}}]),
                    ToolMessage(content, tool_call_id='read-1', name='library_read')]
        with patch.dict(os.environ, {'CORA_CONTEXT_TOKENS':'4096'}):
            fitted = fit_messages(messages, reserve=512)
        self.assertEqual(fitted[1].content, messages[1].content)
        self.assertTrue(_valid_exchange(fitted[1:]))
        self.assertIn('CAPITAN VENTURA', fitted[-1].content)
        self.assertIn('richiamare lunedi', fitted[-1].content)
        self.assertIn('ESTRATTO', fitted[-1].content)
        self.assertLess(sum(message_cost(m) for m in fitted), 4096-1024-512)
        self.assertEqual(messages[-1].content, content)

    def test_write_results_and_user_intent_are_never_shortened(self):
        from core.context_budget import ContextOverflow
        for name in ('library_replace_text', 'unknown'):
            with self.subTest(name=name), patch.dict(os.environ, {'CORA_CONTEXT_TOKENS':'4096'}):
                with self.assertRaises(ContextOverflow):
                    fit_messages([HumanMessage('intent'),AIMessage('',tool_calls=[{'id':'x','name':name,'args':{}}]),ToolMessage('x'*30000,tool_call_id='x',name=name)])


    def test_graph_completes_after_large_read_without_replaying_the_tool(self):
        import graph as supervisor
        from langchain_core.tools import tool
        reads = []
        @tool
        def library_read(relative_path: str) -> str:
            """Read a synthetic customer document."""
            reads.append(relative_path)
            return 'SOURCE_PATH: synthetic.docx\n' + 'Other customer\n'*7000 + 'CAPITAN VENTURA\n24/10/2026: richiamare lunedi'
        class Model:
            def invoke(self, messages):
                if isinstance(messages[-1], ToolMessage):
                    assert 'CAPITAN VENTURA' in messages[-1].content
                    assert 'ESTRATTO' in messages[-1].content
                    return AIMessage('Nel documento sintetico, il 24/10/2026: richiamare lunedi. Fonte parziale.')
                return AIMessage('',tool_calls=[{'id':'read-once','name':'library_read','args':{'relative_path':'synthetic.docx'}}])
        with patch.dict(os.environ, {'CORA_CONTEXT_TOKENS':'4096'}), patch.object(supervisor,'model_with_tools',Model()), patch.object(supervisor,'ensure_runtime_active'), patch.object(supervisor,'_runtime_system_prompt',return_value=('Use sources and disclose partial data.','',[],['library_read'])), patch('core.library_preflight.preload',return_value=''), patch.dict(supervisor.tool_node.tools_by_name,{'library_read':library_read}):
            result = supervisor.graph.invoke({'messages':[HumanMessage('Leggi le ultime note di Capitan Ventura')], 'request_text':'Leggi le ultime note di Capitan Ventura'})
        self.assertIn('richiamare lunedi',result['messages'][-1].content)
        self.assertEqual(reads,['synthetic.docx'])


    def test_prior_thinking_does_not_consume_the_document_budget_or_reach_next_prompt(self):
        call = AIMessage('',tool_calls=[{'id':'r','name':'library_read','args':{}}],additional_kwargs={'reasoning_content':'thinking '*10000})
        messages = [HumanMessage('Read Capitan Ventura'),call,ToolMessage('SOURCE_PATH: synthetic.docx\nCAPITAN VENTURA: richiamare',tool_call_id='r',name='library_read')]
        with patch.dict(os.environ,{'CORA_CONTEXT_TOKENS':'4096'}):
            result=fit_messages(messages,reserve=512)
        self.assertNotIn('reasoning_content',result[1].additional_kwargs)
        self.assertIn('reasoning_content',call.additional_kwargs)
        self.assertEqual(result[-1],messages[-1])
        self.assertTrue(_valid_exchange(result))
