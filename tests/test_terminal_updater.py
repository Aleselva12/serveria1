"""Regression: adding the terminal preserves the installed release and host settings."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from deploy.terminal_updater import add_terminal, prepare


class TerminalUpdaterTests(unittest.TestCase):
    def test_preserves_every_existing_service_and_removes_build(self):
        original = {'services': {'api': {'image': 'sha256:active', 'volumes': [{'source': '/data'}]},
                                  'web': {'environment': {'secret': 'private'}}},
                    'networks': {'default': {'name': 'cora_default'}}}
        before = copy.deepcopy(original)
        result = add_terminal(original, {'image': 'cora-terminal:local', 'build': {'context': '/checkout'}})
        self.assertEqual(original, before)
        for name in before['services']:
            self.assertEqual(result['services'][name], before['services'][name])
        self.assertEqual(result['networks'], before['networks'])
        self.assertNotIn('build', result['services']['terminal'])
        with self.assertRaises(ValueError):
            add_terminal(result, {})

    def test_rejects_exposed_or_privileged_terminal(self):
        for field in ({'ports': ['8022:8022']}, {'privileged': True}, {'network_mode': 'host'}):
            with self.subTest(field=field), self.assertRaises(ValueError):
                add_terminal({'services': {}}, field)

    def test_managed_setup_keeps_images_and_backs_up_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {'CORA_AUTH_MODE': 'tailscale', 'CORA_UI_ORIGINS': 'https://cora.test.ts.net',
                      'CORA_TAILSCALE_LOGIN': 'owner@example.com', 'CORA_TAILSCALE_PROXY_SECRET': 's' * 64}
            snapshot = {'services': {'api': {'image': 'old-api', 'environment': config},
                        'web': {'environment': {**config, 'CORA_TAILSCALE_PROXY_IP': '172.20.0.1'}}}}
            file, images = root / 'compose.json', root / 'images.json'
            original = json.dumps(snapshot).encode()
            file.write_bytes(original)
            image_bytes = b'{"services":{"api":{"image":"sha256:active"}}}'
            images.write_bytes(image_bytes)
            web = {'Config': {'Labels': {'com.docker.compose.project': 'cora',
                   'com.docker.compose.project.config_files': str(file) + ',' + str(images)}}}
            def command(*args):
                if args[:2] == ('docker', 'inspect'):
                    return json.dumps([web])
                if args[0] == 'tailscale':
                    return '{}'
                if '--env-file' in args:
                    return json.dumps({'services': {'terminal': {'image': 'cora-terminal:local',
                                       'build': {'context': str(root)}}}})
                return ''
            args = SimpleNamespace(updater_root=root, container='cora-web-1',
                                   config_root=root / 'terminal', user='ale')
            with patch('deploy.terminal_updater.run', side_effect=command), \
                 patch('deploy.terminal_updater.host_key', return_value='host.docker.internal ssh-ed25519 AAAA\n'), \
                 patch('deploy.terminal_updater.validate', return_value=('172.20.0.1', config['CORA_UI_ORIGINS'])):
                prepare(args, root)
            self.assertEqual(images.read_bytes(), image_bytes)
            after = json.loads(file.read_text())
            after['services'].pop('terminal')
            self.assertEqual(after, snapshot)
            self.assertEqual(next(root.glob('compose.before-terminal-*')).read_bytes(), original)
            if os.name != 'nt':
                self.assertEqual(file.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
