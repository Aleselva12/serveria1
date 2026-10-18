import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from core.context_budget import ContextOverflow, _valid_exchange, message_cost
from core.observability import metadata_event
from programmer_agent.loop_context import fit_programmer_messages, without_thinking
from programmer_agent import programmer_graph as pg, workspace as ws


def call(identity='write', **args):
    return {'name':'programmer_write_file', 'args':args, 'id':identity, 'type':'tool_call'}


class LoopContextTests(unittest.TestCase):
    def test_thinking_removed_only_from_model_projection(self):
        response = AIMessage('', additional_kwargs={'reasoning_content':'private thinking '*4000},
                             tool_calls=[call(workspace_id='test',path='new.py',content='x=1')])
        result = ToolMessage('{"path":"new.py","sha256":"digest","saved":true,"status":"draft"}',
                             name='programmer_write_file',tool_call_id='write')
        original = [SystemMessage('identity'), HumanMessage('Create the exact requested tool'), response, result]
        with patch.dict(os.environ, {'CORA_CONTEXT_TOKENS':'2048'}), patch.object(pg, 'record_metric'):
            projected = fit_programmer_messages(original, tools=[])
        self.assertEqual(projected[1].content, original[1].content)
        self.assertEqual(projected[2].tool_calls, response.tool_calls)
        self.assertEqual(projected[3], result)
        self.assertNotIn('reasoning_content', projected[2].additional_kwargs)
        self.assertIn('reasoning_content', response.additional_kwargs)
        self.assertTrue(_valid_exchange(projected[1:]))

    def test_completed_tool_cycles_compact_without_mutating_source_or_losing_outcomes(self):
        messages=[SystemMessage('identity'),HumanMessage('Keep this exact user request')]
        for i in range(8):
            messages += [AIMessage('',tool_calls=[call(str(i),path=f'generated_{i}.py',content='x'*4000)]),
                ToolMessage(json.dumps({'saved':True,'path':f'generated_{i}.py','sha256':str(i),'status':'draft'}),
                            tool_call_id=str(i),name='programmer_write_file')]
        with patch.dict(os.environ, {'CORA_CONTEXT_TOKENS':'4096'}), patch.object(pg,'record_metric') as record:
            fitted=fit_programmer_messages(messages,tools=[])
        self.assertLess(sum(message_cost(m) for m in fitted), 3072)
        self.assertTrue(any(m.content=='Keep this exact user request' for m in fitted))
        ledger=next(json.loads(m.content) for m in fitted if isinstance(m,AIMessage))
        self.assertEqual(len(ledger['operations']),8)
        self.assertTrue(all(op['result']['saved'] for op in ledger['operations']))
        self.assertEqual(ledger['operations'][-1]['result']['path'],'generated_7.py')
        self.assertEqual(messages[2].tool_calls[0]['args']['content'],'x'*4000)
        self.assertTrue(record.call_args.args[1]['compacted'])

    def test_no_loss_of_mandatory_intent_or_incomplete_exchange(self):
        with patch.dict(os.environ, {'CORA_CONTEXT_TOKENS':'2048'}), patch.object(pg,'record_metric'):
            with self.assertRaises(ContextOverflow):
                fit_programmer_messages([SystemMessage('identity'),HumanMessage('x'*15000)],tools=[])
            with self.assertRaises(ContextOverflow):
                fit_programmer_messages([HumanMessage('Create'),AIMessage('',tool_calls=[call()])],tools=[])

    def test_pending_approval_and_failed_checks_remain_in_compacted_ledger(self):
        from programmer_agent.loop_context import compact_current_turn
        messages=[HumanMessage('create'),AIMessage('',tool_calls=[call()]),
                  ToolMessage('{"status":"pending","approval_id":"approval"}',tool_call_id='write')]
        compacted=compact_current_turn(messages)
        self.assertIn('approval',compacted[-1].content)
        messages[-1]=ToolMessage('{"passed":false,"completed":false,"profile":"syntax"}',tool_call_id='write',status='error')
        result=json.loads(compact_current_turn(messages)[-1].content)['operations'][0]
        self.assertFalse(result['result']['passed']);self.assertEqual(result['status'],'error')

    def test_invalid_arguments_return_schema_without_code_or_tool_execution(self):
        response=AIMessage('',tool_calls=[call(path='new.py',content={'private':'x'*10000})])
        with patch.object(pg._tool_node,'invoke') as execute,patch.object(pg,'record_metric'):
            result=pg.execute_tools({'messages':[response]}, {})['messages'][0]
        execute.assert_not_called()
        error=json.loads(result.content)
        self.assertEqual(error['code'],'invalid_arguments');self.assertFalse(error['executed'])
        self.assertEqual({p['field'] for p in error['problems']},{'workspace_id','content'})
        self.assertEqual(error['fields']['content'],'string')
        self.assertLess(len(result.content),1000);self.assertNotIn('private',result.content)

    def test_argument_repair_disables_thinking_and_rechecks_budget(self):
        model=MagicMock();model.invoke.return_value=AIMessage('No writes yet')
        tool=ToolMessage('{"code":"invalid_arguments","executed":false}',tool_call_id='a',status='error')
        messages=[HumanMessage('Create'),AIMessage('',tool_calls=[call('a')]),tool]
        with patch.object(pg,'programmer_model',return_value=model) as factory,patch.object(pg,'record_metric'):
            pg.call_llm({'system_prompt':'identity','messages':messages})
        self.assertFalse(factory.call_args.kwargs['reasoning'])

    def test_long_graph_creates_real_files_once_then_repairs_malformed_write(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ,{'CORA_PROGRAMMER_WORKSPACE_ROOT':directory+'/work',
                'CORA_CONTEXT_TOKENS':'8192','CORA_CONTEXT_MANAGER_ENABLED':'false'}))
            source=Path(directory)/'source';source.mkdir();(source/'sample.py').write_text('x=1')
            identifier=ws.create('Regression',source)['id']
            stack.enter_context(ws.bind_workspace(identifier))
            stack.enter_context(patch.object(pg,'with_permanent_context',side_effect=lambda p:p))
            stack.enter_context(patch('core.operation_journal.begin',return_value=None))
            stack.enter_context(patch('core.operation_journal.finish'))
            stack.enter_context(patch('core.permissions.policy_overrides',return_value={}))
            stack.enter_context(patch.object(pg,'record_metric'))
            step=0
            class Model:
                model='test-model'
                def bind_tools(self,tools):return self
                def invoke(self,messages):
                    nonlocal step
                    step+=1
                    if step<=5:
                        args={'workspace_id':identifier,'path':f'tool_{step}.py','content':'# '+'x'*4000+'\nvalue=1\n'}
                    elif step==6:
                        args={'path':'last.py','content':{'value':'not a string'}}
                    elif step==7:
                        self_messages=' '.join(str(m.content) for m in messages)
                        self_test.assertIn('invalid_arguments',self_messages)
                        args={'workspace_id':identifier,'path':'last.py','content':'value=2\n'}
                    else:
                        return AIMessage('Draft files saved; not activated')
                    return AIMessage('',tool_calls=[call(str(step),**args)],additional_kwargs={'reasoning_content':'thought '*3000})
            self_test=self
            stack.enter_context(patch.object(pg,'get_chat_model',return_value=Model()))
            # Keep schema cost within the deliberately small test context.
            tools=[t for t in pg.PROGRAMMER_TOOLS if t.name=='programmer_write_file']
            stack.enter_context(patch.object(pg,'PROGRAMMER_TOOLS',tools))
            result=pg.create_programmer_graph().invoke({'messages':[HumanMessage('Create draft tools')]},config={'recursion_limit':30})
            self.assertEqual(step,8)
            self.assertEqual(ws.read(identifier,'last.py')['content'],'value=2\n')
            self.assertEqual(ws.diff(identifier)['total_changes'],6)
            self.assertEqual(sum(isinstance(m,ToolMessage) and m.status=='error' for m in result['messages']),1)
            self.assertIn('non certifica',result['messages'][-1].content)

    def test_diagnostic_metrics_survive_projection_without_private_text(self):
        event=metadata_event({'type':'programmer.context_call','payload':{
            'prompt_eval_count':6561,'error_type':'ContextOverflow','content':'private','done_reason':'stop'}})
        self.assertEqual(event['payload'],{'prompt_eval_count':6561,'error_type':'ContextOverflow','done_reason':'stop'})
