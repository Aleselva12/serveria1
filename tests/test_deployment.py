"""Host operations protect existing credentials and reject incomplete backups."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('deploy_manage',Path(__file__).resolve().parents[1]/'deploy/manage.py')
manage=importlib.util.module_from_spec(spec);spec.loader.exec_module(manage)


class HostDeploymentTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "Debian deployment checks POSIX UID/GID and permissions")
    def test_init_creates_private_unique_credentials_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'deploy').mkdir()
            (root/'deploy/deploy.env.example').write_text((manage.ROOT/'deploy/deploy.env.example').read_text())
            with patch.object(manage,'ROOT',root),patch.object(manage,'ENV',root/'deploy.env'),patch.object(manage.os,'getuid',return_value=1000),patch.object(manage.os,'getgid',return_value=1000):
                manage.init();content=(root/'deploy.env').read_text()
                self.assertNotIn('GENERATED_BY_INIT',content)
                self.assertEqual(os.stat(root/'deploy.env').st_mode & 0o777,0o600)
                self.assertTrue((root/'state/audio/_transcripts').is_dir())
                with self.assertRaises(ValueError):manage.init()
                self.assertEqual((root/'deploy.env').read_text(),content)


    def test_google_calendar_auth_uses_active_image_without_compose_port(self):
        from subprocess import CompletedProcess
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            state=root/'state';state.mkdir()
            env=root/'deploy.env';env.write_text('CORA_STATE_ROOT='+str(state)+'\n')
            calls=[]
            def compose(*args,**kwargs):
                self.assertEqual(args,('ps','-q','api'))
                return CompletedProcess(['docker','compose'],0,stdout='api-container\n')
            def run(command,**kwargs):
                calls.append(command)
                if command[:3]==['docker','inspect','--format={{.Image}}']:
                    return CompletedProcess(command,0,stdout='sha256:active-api\n')
                return CompletedProcess(command,0,stdout='')
            with patch.object(manage,'ROOT',root),patch.object(manage,'ENV',env),patch.object(manage,'compose',side_effect=compose),patch.object(manage.subprocess,'run',side_effect=run):
                manage.google_calendar_auth('example@example.com',8765)
            launch=calls[-1]
            self.assertEqual(launch[:5],['docker','run','--rm','--network','host'])
            self.assertIn('type=bind,src='+str(state)+',dst=/state',launch)
            self.assertIn('sha256:active-api',launch)
            self.assertEqual(launch[launch.index('--host')+1],'127.0.0.1')
            self.assertEqual(launch[launch.index('--port')+1],'8765')
            self.assertEqual(launch[launch.index('--login-hint')+1],'example@example.com')

    def test_corrupt_or_incomplete_backup_is_rejected_before_restore_stops_services(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)
            for name in ('database.dump','state.tar.gz','deploy.env'):(path/name).write_bytes(b'original')
            manifest={'version':1,'sha256':{name:manage.digest(path/name) for name in ('database.dump','state.tar.gz','deploy.env')}}
            (path/'manifest.json').write_text(json.dumps(manifest));manage.check_backup(path)
            (path/'database.dump').write_bytes(b'corrupt')
            with patch.object(manage,'compose') as compose:
                with self.assertRaises(ValueError):manage.restore(path)
                compose.assert_not_called()

    def test_backup_failure_keeps_application_stopped_and_has_no_valid_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'snapshot'
            with patch.object(manage,'compose',side_effect=[None,OSError('dump failure')]) as compose:
                with self.assertRaises(OSError):manage.backup(path)
                self.assertEqual(compose.call_count,2)
                self.assertEqual(compose.call_args_list[0].args,('stop','web','api'))
            self.assertFalse((path/'manifest.json').exists())

    def test_backup_preserves_override_order_through_restart(self):
        from subprocess import CompletedProcess
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env = root/'deploy.env'; env.write_text('example')
            overrides = (root/'nas.yml', root/'local.yml')
            commands = []
            def run(command, **kwargs):
                commands.append(command)
                if 'stdout' in kwargs:
                    kwargs['stdout'].write(b'backup')
                return CompletedProcess(command, 0, stdout='[]')
            with patch.object(manage, 'ENV', env), patch.object(manage, 'COMPOSE_FILES', overrides), patch.object(manage.subprocess, 'run', side_effect=run):
                manage.backup(root/'backup')
            docker = [cmd for cmd in commands if cmd[0] == 'docker']
            for command in docker:
                self.assertEqual([command[i+1] for i, arg in enumerate(command) if arg == '-f'], [str(manage.ROOT/'compose.yml'), *map(str, overrides)])
            self.assertEqual(docker[-1][-5:], ['up', '-d', '--wait', 'api', 'web'])
            manage.check_backup(root/'backup')
