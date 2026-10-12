"""Protect diagnostic confidentiality and prevent false certification."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('priority_checks', Path(__file__).resolve().parents[1]/'deploy/priority_checks.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


class PriorityChecksTests(unittest.TestCase):
    def test_successful_probe_does_not_hide_failed_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/'probe.json'
            with patch.object(checks, 'inspect_host', return_value=({'ok': False}, 'api')), \
                 patch.object(checks, 'api_probe', return_value={'ok': True}), patch('builtins.print'):
                code = checks.main(['ollama', '--output', str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(code, 1)
            self.assertTrue(report['probe']['ok'])
            self.assertFalse(report['ok'])

    def test_trace_converts_provider_units_without_adding_nested_nodes(self):
        import types
        fake = types.ModuleType('core.execution_traces')
        fake.read_runs = lambda **kwargs: [{'id': 'id', 'status': 'completed', 'duration_ms': 1000,
            'metrics': {'node_ms': 2000, 'models': [{'duration_ms': 900,
                'prompt_eval_duration': 600000000, 'eval_duration': 300000000}]}}]
        with patch.dict('sys.modules', {'core.execution_traces': fake}), patch('builtins.print') as output:
            exec(checks.trace_source('11111111-1111-4111-8111-111111111111'), {})
        report = json.loads(output.call_args.args[0])
        run = report['runs'][0]
        self.assertEqual(run['summary']['model_share_percent'], 90)
        self.assertEqual(run['summary']['model_calls'], 1)
        self.assertEqual(run['timings']['models'][0]['provider_ms']['prompt_eval_duration'], 600)
        self.assertEqual(report['scope'], 'runtime_completion_not_task_correctness')

    def test_inspect_allowlist_excludes_environment_and_health_logs(self):
        data = {'Id':'container', 'Image':'sha256:image',
                'Config':{'Image':'cora-api:local', 'Env':['SECRET=private']},
                'State':{'Running':True,'Health':{'Status':'healthy','Log':['private']}},
                'Mounts':[{'Source':'/srv/state','Destination':'/state','RW':True,'Type':'bind'}]}
        result = checks.container_summary(data)
        self.assertNotIn('private', json.dumps(result))
        self.assertEqual(result['mounts'][0]['Destination'], '/state')

    def test_failed_command_does_not_expose_raw_output(self):
        with patch.object(checks.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, 'password', 'token')):
            with self.assertRaisesRegex(checks.ProbeError, '^command_exit_1$'):
                checks.command(['docker','inspect','example'])

    def test_missing_docker_saves_failure_and_does_not_overwrite_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)/'report.json'
            with patch.object(checks, 'command', side_effect=checks.ProbeError('FileNotFoundError')), patch('builtins.print'):
                self.assertEqual(checks.main(['inspect','--root',temporary,'--output',str(output)]), 1)
                report = json.loads(output.read_text())
                self.assertFalse(report['ok'])
                with self.assertRaises(FileExistsError):
                    checks.main(['inspect','--root',temporary,'--output',str(output)])
            self.assertEqual(json.loads(output.read_text()), report)

    def test_embedded_scripts_compile_and_trace_rejects_invalid_identifier(self):
        for source in (checks.INVENTORY, checks.OLLAMA, checks.programmer_source(), checks.trace_source('11111111-1111-4111-8111-111111111111'), checks.ISOLATION_TEST):
            compile(source, '<probe>', 'exec')
        with self.assertRaises(ValueError): checks.trace_source("'; print('private')")

    def test_inventory_prevents_legacy_doctor_from_creating_missing_directories(self):
        import types
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = root/'missing'
            def inspect():
                root.mkdir(exist_ok=True)
                try: missing.mkdir(parents=True, exist_ok=True)
                except FileNotFoundError: return {'ok':False}
                return {'ok':True}
            doctor = types.ModuleType('deploy.doctor'); doctor.inspect = inspect
            models = types.ModuleType('core.models')
            models.ROLE_MODEL_ENV = {'programmer':'CORA_MODEL_PROGRAMMER'}
            models.get_model_name = lambda role: 'test'
            programmer = types.ModuleType('programmer_agent')
            programmer.workspace = types.SimpleNamespace(root=lambda:root)
            programmer.releases = types.SimpleNamespace(status=lambda:{'available':True,'active_commit':'abc'})
            with patch.dict('sys.modules', {'deploy.doctor':doctor,'core.models':models,'programmer_agent':programmer}), patch('builtins.print') as output:
                exec(checks.INVENTORY, {})
            self.assertFalse(missing.exists())
            report = json.loads(output.call_args.args[0])
            self.assertFalse(report['doctor']['ok'])
            self.assertEqual(report['bridge']['commit'], 'abc')

    def test_trace_keeps_metrics_but_excludes_private_payloads(self):
        import types
        fake = types.ModuleType('core.execution_traces')
        fake.read_runs = lambda **kwargs: [{'id':'id','status':'completed','duration_ms':100,
            'thread_id':'private','events':[{'content':'private'}],
            'metrics':{'queue_ms':2,'context_ms':3,'output':'private',
                       'configuration':{'model':'test','ollama_base_url':'private'},
                       'models':[{'role':'programmer','duration_ms':80,'response':'private'}]}}]
        with patch.dict('sys.modules', {'core.execution_traces':fake}), patch('builtins.print') as output:
            exec(checks.trace_source('11111111-1111-4111-8111-111111111111'), {})
        report = json.loads(output.call_args.args[0])
        self.assertNotIn('private', json.dumps(report))
        self.assertEqual(report['runs'][0]['timings']['queue_ms'], 2)


if __name__ == '__main__': unittest.main()
