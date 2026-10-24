import json
import os
import unittest
from unittest.mock import patch
from core.model_profiles import parse_profile, profile_for, _cache
from core.models import get_chat_model

RESOLVED = {'role':'supervisor','model':'model:8b','machine_id':'local','source':'default','configuration_id':'test'}

class ModelProfileTests(unittest.TestCase):
    def tearDown(self):
        _cache.clear()

    def test_context_and_capabilities_are_model_specific_not_size_guesses(self):
        with patch.dict(os.environ, {'CORA_CONTEXT_TOKENS':'16384'}):
            small = parse_profile({'capabilities':['completion'], 'model_info':{'x.context_length':4096}}, RESOLVED)
            large = parse_profile({'capabilities':['tools','thinking'], 'model_info':{'x.context_length':131072}}, RESOLVED)
        self.assertEqual((small['context_tokens'],small['tools'],small['thinking_values']),(4096,False,[False]))
        self.assertEqual((large['context_tokens'],large['tools']),(16384,True))
        unknown = parse_profile({}, RESOLVED)
        self.assertIsNone(unknown['tools']);self.assertEqual(unknown['thinking_values'],[])

    def test_named_thinking_levels_do_not_become_booleans(self):
        info = parse_profile({'capabilities':['tools','thinking'],'thinking':{'values':['low','medium','high'],'default':'low'}}, RESOLVED)
        with patch('core.models.resolve_model',return_value=RESOLVED):
            model = get_chat_model(model_profile=info,reasoning='high')
            self.assertEqual(model._chat_params([])['think'],'high')
            default = get_chat_model(model_profile=info)
            self.assertNotIn('think', default._chat_params([]))
            unsupported = get_chat_model(model_profile=info,reasoning=True)
            self.assertNotIn('think', unsupported._chat_params([]))

    def test_no_tool_model_can_chat_but_cannot_bind_tools(self):
        from core.model_profiles import ModelToolsUnsupported
        from langchain_core.tools import tool
        @tool
        def read():
            """Synthetic read."""
            return 'ok'
        with patch('core.models.resolve_model',return_value=RESOLVED):
            model = get_chat_model(model_profile=parse_profile({'capabilities':['completion']},RESOLVED))
        self.assertEqual(model._chat_params([])['think'],False)
        with self.assertRaises(ModelToolsUnsupported):model.bind_tools([read])

    def test_old_worker_metadata_is_unknown_and_never_falls_back_local(self):
        remote = {**RESOLVED,'machine_id':'desktop'}
        with patch('core.agent_models.remote_machine',return_value={'id':'desktop'}), patch('core.machines_api._worker_call',side_effect=RuntimeError('old bridge')) as call, patch('core.ollama_transport.urlopen') as local:
            result = profile_for(remote)
        self.assertFalse(result['verified']);self.assertIsNone(result['tools'])
        self.assertEqual(result['transport'],'buffered');local.assert_not_called();self.assertEqual(call.call_count,1)

    def test_cache_is_separate_for_machine_and_model(self):
        from io import BytesIO
        with patch('core.ollama_transport.urlopen',side_effect=lambda *a,**k:BytesIO(json.dumps({'capabilities':['tools']}).encode())) as fetch:
            profile_for(RESOLVED);profile_for(RESOLVED)
            profile_for({**RESOLVED,'model':'other'})
        self.assertEqual(fetch.call_count,2)
