import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from core import auth
from deploy.tailscale_login import validate, update_env


class TailscaleAuthTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'CORA_AUTH_MODE': 'tailscale', 'CORA_TAILSCALE_LOGIN': 'owner@example.com',
            'CORA_TAILSCALE_PROXY_SECRET': 'a'*64,
            'CORA_UI_ORIGINS': 'https://server.example.ts.net'})
        self.env.start(); self.addCleanup(self.env.stop)
        app = FastAPI(); app.add_middleware(auth.AuthMiddleware); app.include_router(auth.router)
        @app.get('/private')
        def private(request: Request): return request.state.user
        @app.post('/write')
        def write(): return {'ok': True}
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.headers = {'X-Cora-Tailscale-Login': 'owner@example.com', 'X-Cora-Proxy-Secret': 'a'*64}
        self.owner = {'id': 'existing-owner-id', 'username': 'existing-name'}
        from unittest.mock import MagicMock
        conn = MagicMock(); conn.execute.return_value.fetchone.return_value = self.owner
        @contextmanager
        def database(): yield conn
        db = patch.object(auth, 'db_connection', database); db.start(); self.addCleanup(db.stop)

    def test_owner_enters_without_cookie_and_retains_audit_identity(self):
        r = self.client.get('/auth/status', headers=self.headers)
        self.assertEqual(r.json(), {'authenticated': True, 'username': 'existing-name', 'mode': 'tailscale'})
        self.assertNotIn('set-cookie', r.headers)
        self.assertEqual(self.client.get('/private', headers=self.headers).json(), self.owner)

    def test_forged_headers_wrong_owner_duplicate_identity_and_cookies_fail_closed(self):
        for headers in [{}, {'Tailscale-User-Login': 'owner@example.com'},
                        {'Cookie': 'cora_session=previous-session'},
                        {**self.headers, 'X-Cora-Proxy-Secret': 'wrong'},
                        {**self.headers, 'X-Cora-Tailscale-Login': 'other@example.com'},
                        {**self.headers, 'X-Cora-Tailscale-Login': 'owner@example.com.evil'},
                        [('X-Cora-Proxy-Secret', 'a'*64), ('X-Cora-Tailscale-Login', 'owner@example.com'),
                         ('X-Cora-Tailscale-Login', 'owner@example.com')]]:
            with self.subTest(headers=headers):
                self.assertEqual(self.client.get('/private', headers=headers).status_code, 401)
                self.assertFalse(self.client.get('/auth/status', headers=headers).json()['authenticated'])

    def test_browser_write_protection_remains_required(self):
        self.assertEqual(self.client.post('/write', headers=self.headers).status_code, 403)
        headers = {**self.headers, 'X-Cora-Client': 'ui', 'Origin': 'https://evil.example'}
        self.assertEqual(self.client.post('/write', headers=headers).status_code, 403)
        headers['Origin'] = 'https://server.example.ts.net'
        self.assertEqual(self.client.post('/write', headers=headers).status_code, 200)

    def test_password_login_disabled_and_logout_explained(self):
        headers = {**self.headers, 'X-Cora-Client': 'ui'}
        self.assertEqual(self.client.post('/auth/login', headers=headers,
                        json={'username': 'old', 'password': 'password'}).status_code, 403)
        self.assertEqual(self.client.post('/auth/logout', headers=headers).status_code, 409)

    def test_missing_configuration_and_invalid_mode_fail_closed(self):
        for env in [{'CORA_TAILSCALE_LOGIN': ''}, {'CORA_TAILSCALE_PROXY_SECRET': ''}, {'CORA_AUTH_MODE': 'off'}]:
            with patch.dict(os.environ, env):
                self.assertEqual(self.client.get('/private', headers=self.headers).status_code, 503)
                self.assertEqual(self.client.get('/auth/status', headers=self.headers).status_code, 503)

    def test_password_mode_keeps_existing_cookie_login(self):
        with patch.dict(os.environ, {'CORA_AUTH_MODE': 'password'}), patch.object(auth, 'session_user', return_value=self.owner):
            self.assertEqual(self.client.get('/private').status_code, 200)
            self.assertEqual(self.client.get('/auth/status').json()['mode'], 'password')
        with patch.dict(os.environ, {'CORA_AUTH_MODE': 'password'}), patch.object(auth, 'session_user', return_value=None):
            self.assertEqual(self.client.get('/private', headers=self.headers).status_code, 401)


class SetupTests(unittest.TestCase):
    def fixtures(self):
        return ({'HostConfig': {'PortBindings': {'80/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8090'}]}},
                 'NetworkSettings': {'Networks': {'cora_default': {'Gateway': '172.20.0.1'}}}},
                {'Web': {'server.example.ts.net:443': {'Handlers': {'/': {'Proxy': 'http://127.0.0.1:8090'}}}}})

    def test_private_serve_only(self):
        web, serve = self.fixtures()
        self.assertEqual(validate('owner@example.com', 'https://server.example.ts.net', web, serve),
                         ('172.20.0.1', 'https://server.example.ts.net'))
        serve['AllowFunnel'] = {'server.example.ts.net:443': True}
        with self.assertRaises(ValueError): validate('owner@example.com', 'https://server.example.ts.net', web, serve)
        web, serve = self.fixtures(); web['HostConfig']['PortBindings']['80/tcp'][0]['HostIp'] = '0.0.0.0'
        with self.assertRaises(ValueError): validate('owner@example.com', 'https://server.example.ts.net', web, serve)

    def test_bad_origin_proxy_target_and_login_rejected(self):
        web, serve = self.fixtures()
        for origin in ['http://server.example.ts.net', 'https://evil.example', 'https://server.example.ts.net/path']:
            with self.assertRaises(ValueError): validate('owner@example.com', origin, web, serve)
        with self.assertRaises(ValueError): validate('owner@example.com\nINJECT=true', 'https://server.example.ts.net', web, serve)
        serve['Web']['server.example.ts.net:443']['Handlers']['/']['Proxy'] = 'http://127.0.0.1:9999'
        with self.assertRaises(ValueError): validate('owner@example.com', 'https://server.example.ts.net', web, serve)

    def test_configuration_preserves_unrelated_values_and_replaces_duplicates(self):
        before = 'CORA_POSTGRES_PASSWORD=secret\nCORA_AUTH_MODE=password\nexport CORA_AUTH_MODE=old\nCORA_FILE_ROOTS=original\n'
        after = update_env(before, {'CORA_AUTH_MODE': 'tailscale'})
        self.assertIn('CORA_POSTGRES_PASSWORD=secret\n', after)
        self.assertIn('CORA_FILE_ROOTS=original\n', after)
        self.assertEqual(after.count('CORA_AUTH_MODE='), 1)

    def test_main_keeps_compose_overrides_and_private_backup(self):
        import json
        import tempfile
        from pathlib import Path
        from deploy import tailscale_login as setup
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for file in ('compose.yml', 'compose.nas.yml'): (root/file).write_text('services: {}')
            original = 'CORA_POSTGRES_PASSWORD=keep-me\nCORA_FILE_ROOTS=nas\n'
            (root/'deploy.env').write_text(original)
            web, serve = self.fixtures()
            web['Config'] = {'Labels': {'com.docker.compose.project.working_dir': str(root),
                'com.docker.compose.project.config_files': f'{root}/compose.yml,{root}/compose.nas.yml',
                'com.docker.compose.project': 'cora'}}
            commands = []
            def run(*args):
                commands.append(args)
                if args[:2] == ('docker', 'inspect'): return json.dumps([web])
                if args[:2] == ('tailscale', 'serve'): return json.dumps(serve)
                self.assertIn(str(root/'compose.nas.yml'), args)
                if 'config' in args:
                    env = dict(line.split('=', 1) for line in Path(args[args.index('--env-file')+1]).read_text().splitlines())
                    return json.dumps({'services': {
                        'api': {'environment': env},
                        'web': {'environment': env, 'ports': [{'host_ip': '127.0.0.1'}]}}})
                return '1\n'
            with patch.object(setup, 'ROOT', root), patch.object(setup, 'run', side_effect=run), patch('sys.argv',
                    ['tailscale_login.py', '--login', 'owner@example.com', '--origin', 'https://server.example.ts.net']):
                setup.main()
            self.assertIn('CORA_AUTH_MODE=tailscale', (root/'deploy.env').read_text())
            self.assertIn('CORA_POSTGRES_PASSWORD=keep-me', (root/'deploy.env').read_text())
            backup = next(root.glob('deploy.env.before-tailscale-*'))
            self.assertEqual(backup.read_text(), original)
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
            self.assertEqual((root/'deploy.env').stat().st_mode & 0o777, 0o600)
            self.assertFalse(list(root.glob('.tailscale-env-*')))
            self.assertFalse(any('up' in command for command in commands))
