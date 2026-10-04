import json
import unittest
from unittest.mock import patch
from core.capability_contracts import CapabilityResult
from core.governance import agent_tool, execute_capability, executables, CapabilityExecutionError
from core.permissions import require_permission
from core.run_states import EffectUncertain

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.keys=set(executables)
        self.begin = patch('core.operation_journal.begin',return_value=None);self.begin.start()
        self.finish = patch('core.operation_journal.finish',return_value=None);self.finish.start()
    def tearDown(self):
        self.begin.stop(); self.finish.stop()
        for key in set(executables)-self.keys: executables.pop(key)

    def test_input_is_strict_defaults_are_normalized_and_adapter_uses_same_service(self):
        effects=[]
        @agent_tool('supervisor', capability='contract_input_test', actions=('calculate',), effect='compute', retry='safe')
        def calc(value:int, suffix:str='default')->str:
            """Test a typed computation."""
            effects.append((value,suffix));return str(value)
        for payload in [{'value':'2'},{'value':2,'actor':'admin'},{'value':2,'user_approved':True}]:
            outcome=execute_capability('supervisor.contract_input_test',payload)
            self.assertEqual(outcome.status,'error');self.assertEqual(outcome.error.code,'ValidationError')
        self.assertEqual(effects,[])
        result=execute_capability('supervisor.contract_input_test',{'value':2})
        self.assertEqual(result.status,'ok');self.assertEqual(result.value,2)
        self.assertEqual(calc.invoke({'value':3}),'3')
        self.assertEqual(effects,[(2,'default'),(3,'default')])
        self.assertNotIn('native',result.model_dump());CapabilityResult.model_validate(result.model_dump())
        entry=next(e for e in executables.values() if e['tool'] is calc)
        self.assertFalse(entry['contract'].input_schema['additionalProperties'])

    def test_undeclared_permission_and_actor_change_are_denied(self):
        effects=[]
        @agent_tool('supervisor', capability='contract_undeclared_test', actions=('calculate',), effect='write', retry='never')
        def undeclared()->str:
            """An implementation cannot add an undeclared permission."""
            require_permission('supervisor','remember_memory');effects.append(True);return 'ok'
        @agent_tool('supervisor', capability='contract_actor_test', actions=('calculate',), effect='write', retry='never')
        def actor()->str:
            """An implementation cannot switch actor."""
            require_permission('structure_agent','inspect_runtime');effects.append(True);return 'ok'
        for tool in [undeclared,actor]:
            with self.assertRaises((CapabilityExecutionError,EffectUncertain)):tool.invoke({})
        self.assertEqual(effects,[])

    def test_tool_cannot_approve_itself_and_conditional_block_does_not_block_other_branch(self):
        effects=[]
        @agent_tool('supervisor', capability='contract_self_grant_test', actions=('calculate',), conditional_actions=('remember_memory',), effect='write',retry='never')
        def self_grant()->str:
            """An explicit user_approved argument from a tool is untrusted."""
            require_permission('supervisor','remember_memory',user_approved=True);effects.append(True);return 'ok'
        with patch('core.permissions.policy_overrides',return_value={('supervisor','remember_memory'):'confirm'}),patch('core.governance.propose',return_value={'id':'proposal'}):
            self.assertEqual(json.loads(self_grant.invoke({}))['status'],'pending')
        self.assertEqual(effects,[])
        @agent_tool('supervisor', capability='contract_conditional_test', actions=('calculate',),conditional_actions=('remember_memory',),effect='write',retry='never')
        def conditional(write:bool=False)->str:
            """A blocked branch is checked only when selected."""
            if write:require_permission('supervisor','remember_memory');effects.append(True)
            return 'ok'
        with patch('core.permissions.policy_overrides',return_value={('supervisor','remember_memory'):'blocked'}):
            self.assertEqual(conditional.invoke({}),'ok')
            self.assertEqual(execute_capability('supervisor.contract_conditional_test',{'write':True}).status,'error')
        self.assertEqual(effects,[])

    def test_unknown_required_action_and_blocked_action_prevent_effect_before_confirmation(self):
        effects=[]
        @agent_tool('supervisor',actions=('remember_memory','calculate'),effect='write',retry='never')
        def blocked()->str:
            """A blocked required action prevents a proposal for a different action."""
            effects.append(True);return 'ok'
        with patch('core.permissions.policy_overrides',return_value={('supervisor','remember_memory'):'confirm',('supervisor','calculate'):'blocked'}),patch('core.governance.propose') as propose:
            result=execute_capability('supervisor.blocked',{})
            self.assertEqual(result.status,'error');propose.assert_not_called()
        self.assertEqual(effects,[])

    def test_reported_errors_and_wrong_output_types_are_not_success(self):
        @agent_tool('supervisor',actions=('calculate',),effect='compute',retry='safe')
        def reported()->str:
            """A structured domain error stays an error."""
            return json.dumps({'status':'error','error':'failed'})
        @agent_tool('supervisor',actions=('calculate',),effect='compute',retry='safe')
        def wrong()->dict:
            """Incorrect implementation output violates the contract."""
            return 'wrong type'
        self.assertEqual(execute_capability('supervisor.reported',{}).error.code,'ToolReportedError')
        self.assertEqual(execute_capability('supervisor.wrong',{}).error.code,'ValidationError')

    def test_invalid_pending_and_failed_proposal_emit_error_outcomes(self):
        @agent_tool('supervisor', actions=('calculate',), effect='compute', retry='safe')
        def missing_approval_id() -> dict:
            """An incomplete pending outcome cannot pass the common contract."""
            return {'status':'pending'}
        with patch('core.governance.bus.publish') as publish:
            result = execute_capability('supervisor.missing_approval_id', {})
            self.assertEqual(result.status, 'error')
            self.assertEqual(publish.call_args.kwargs['payload']['status'], 'error')
        @agent_tool('supervisor', actions=('remember_memory',), effect='write', retry='never')
        def unavailable_proposal_store() -> str:
            """Do not execute if the confirmation cannot be stored."""
            self.fail('Effect must not run')
        with patch('core.permissions.policy_overrides',return_value={('supervisor','remember_memory'):'confirm'}), patch('core.governance.propose',side_effect=RuntimeError('private database detail')):
            result = execute_capability('supervisor.unavailable_proposal_store', {})
        self.assertEqual(result.status, 'error')
        self.assertNotIn('private database detail', result.model_dump_json())

    def test_identity_collisions_and_safe_writes_are_rejected(self):
        @agent_tool('supervisor',capability='stable_test',actions=('calculate',),effect='compute',retry='safe')
        def first()->str:
            """Stable identity."""
            return 'ok'
        with self.assertRaises(ValueError):
            @agent_tool('supervisor',capability='stable_test',actions=('calculate',),effect='compute',retry='safe')
            def second()->str:
                """Duplicate identity."""
                return 'ok'
        with self.assertRaises(ValueError):
            @agent_tool('supervisor',actions=('remember_memory',),effect='write',retry='safe')
            def unsafe()->str:
                """Unsafe repeat declaration."""
                return 'ok'
