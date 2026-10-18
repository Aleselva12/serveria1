import asyncio
import json
import unittest
from unittest.mock import patch
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from core.models import ConfiguredChatOllama, preserve_tool_argument_types
from programmer_agent.programmer_tools import programmer_write_file


class OllamaToolArgumentTests(unittest.TestCase):
    def raw(self, arguments):
        return {'message':{'content':'','tool_calls':[{'function':{
            'name':'programmer_write_file','arguments':arguments}}]},'done':True,'done_reason':'stop'}

    def test_sync_native_stream_keeps_json_file_text_byte_for_byte(self):
        content=' {\n  "nodes": [], "edges": [], "note": "caffè"\n}\n'
        args={'workspace_id':'selected','path':'draft.json','content':content}
        response=self.raw(args)
        model=ConfiguredChatOllama(model='test',reasoning=True)
        with patch.object(ChatOllama,'_create_chat_stream',return_value=iter([response])):
            result=model.invoke([HumanMessage('save draft')])
        parsed=result.tool_calls[0]['args']
        self.assertEqual(parsed,args)
        self.assertEqual(programmer_write_file.args_schema.model_validate(parsed).content,content)
        self.assertIs(response['message']['tool_calls'][0]['function']['arguments'],args)

    def test_async_native_stream_also_preserves_string_and_structured_types(self):
        args={'content':'[1, 2, 3]','data':{'nodes':[]},'files':['a.py'],'path':'x.json'}
        async def stream(*unused,**kwargs):
            yield self.raw(args)
        async def invoke():
            with patch.object(ChatOllama,'_acreate_chat_stream',new=stream):
                return await ConfiguredChatOllama(model='test').ainvoke([HumanMessage('test')])
        response=asyncio.run(invoke())
        self.assertEqual(response.tool_calls[0]['args'],args)

    def test_encoded_envelope_is_not_double_parsed_and_real_type_errors_stay_errors(self):
        for arguments in ({'content':{'invalid':'object'}}, json.dumps({'content':'{"x":1}'})):
            raw=self.raw(arguments)
            projected=preserve_tool_argument_types(raw)
            envelope=projected['message']['tool_calls'][0]['function']['arguments']
            self.assertEqual(json.loads(envelope),arguments if isinstance(arguments,dict) else json.loads(arguments))
        self.assertEqual(preserve_tool_argument_types('metadata'),'metadata')
        self.assertEqual(preserve_tool_argument_types({'done':True}),{'done':True})
