import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from core import auth, desktop_updates as updates


class DesktopAuthTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'CORA_AUTH_MODE': 'desktop'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.owner = {'id': 'existing-owner', 'username': 'owner'}
        conn = MagicMock(); conn.execute.return_value.fetchone.return_value = self.owner
        database = patch.object(auth, 'db_connection')
        self.database = database.start(); self.addCleanup(database.stop)
        self.database.return_value.__enter__.return_value = conn
        app = FastAPI(); app.add_middleware(auth.AuthMiddleware); app.include_router(auth.router)
        app.include_router(updates.router)
        @app.get('/private')
        def private(request: Request): return request.state.user
        @app.post('/write')
        def write(): return {'ok': True}
        self.client = TestClient(app, base_url='http://127.0.0.1:8000', client=('127.0.0.1', 6000))
        self.addCleanup(self.client.close)

    def test_local_enters_without_old_login_preserves_owner(self):
        self.assertEqual(self.client.get('/private').json(), self.owner)
        self.assertTrue(self.client.get('/auth/status').json()['authenticated'])
        self.assertEqual(self.client.post('/auth/login', headers={'X-Cora-Client':'ui'},
                         json={'username':'x','password':'old'}).status_code, 403)

    def test_host_origin_forwarding_and_remote_addresses_fail_closed(self):
        for headers in ({'Host':'evil.example'}, {'Origin':'https://evil.example'},
                        {'X-Forwarded-For':'127.0.0.1'}, {'Forwarded':'for=127.0.0.1'}):
            self.assertEqual(self.client.get('/private', headers=headers).status_code, 401)
        self.client._transport.client = ('192.168.1.5', 6000)
        self.assertEqual(self.client.get('/private').status_code, 401)

    def test_browser_writes_require_header_and_origin(self):
        self.assertEqual(self.client.post('/write').status_code, 403)
        self.assertEqual(self.client.post('/write', headers={'X-Cora-Client':'ui',
                         'Origin':'https://evil.example'}).status_code, 403)
        self.assertEqual(self.client.post('/write', headers={'X-Cora-Client':'ui',
                         'Origin':'http://127.0.0.1:5173'}).status_code, 200)

    def test_update_routes_protected_and_do_not_launch_on_get(self):
        with patch.object(updates, 'desktop', return_value=True), patch.object(updates.threading, 'Thread') as thread:
            self.assertEqual(self.client.get('/api/v1/system/update').status_code, 200)
            thread.assert_not_called()
            self.assertEqual(self.client.post('/api/v1/system/update/prepare').status_code, 403)
            with patch.dict(updates.JOB, {'status':'running'}, clear=True):
                self.assertEqual(self.client.post('/api/v1/system/update/prepare', headers={'X-Cora-Client':'ui'}).status_code, 409)
        with patch.object(updates, 'desktop', return_value=False), \
             patch('programmer_agent.releases.status', return_value={'available': False, 'reason': 'Non configurato', 'jobs': []}):
            response = self.client.get('/api/v1/system/update')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['platform'], 'server')
            self.assertIs(response.json()['available'], False)
            self.assertEqual(response.json()['jobs'], [])
            self.assertEqual(self.client.post('/api/v1/system/update/prepare', headers={'X-Cora-Client':'ui'}).status_code, 409)
            self.assertEqual(self.client.post('/api/v1/system/update/server/prepare').status_code, 403)
            self.assertEqual(self.client.post('/api/v1/system/update/server/prepare', headers={'X-Cora-Client':'ui'}).status_code, 503)

    def test_setup_preserves_owner_or_creates_unusable_random_password(self):
        with patch.object(auth, 'interactive_provision') as prompt, patch.object(auth, 'provision') as provision:
            auth.setup_if_needed(); provision.assert_not_called(); prompt.assert_not_called()
            self.database.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = None
            auth.setup_if_needed(); prompt.assert_not_called()
            self.assertGreater(len(provision.call_args.args[1]), 32)


class CandidateTests(unittest.TestCase):
    def archive(self, extra=None):
        result = io.BytesIO()
        with zipfile.ZipFile(result, 'w') as archive:
            for name in ['AVVIO.cmd', 'requirements-test.txt', 'frontend/package-lock.json']:
                archive.writestr('serveria/' + name, '{}')
            if extra: archive.writestr(*extra)
        return result.getvalue()

    def test_extract_rejects_traversal_private_state_and_duplicate_paths(self):
        for name in ('serveria/../../escape.py','serveria/C:/escape.py','serveria/..\\escape.py',
                     'serveria/.env','serveria/data/run.json','serveria/AVVIO.cmd'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError): updates.extract_candidate(self.archive((name, 'x')), Path(tmp))
                self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_candidate_checks_before_ready_and_keeps_current_installation(self):
        for failure in (False, True):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)/'current'; root.mkdir(); (root/'data').mkdir()
                (root/'sample.py').write_text('original')
                with patch.object(updates, 'ROOT', root), patch.object(updates, 'download', side_effect=[
                     b'{"sha":"' + b'a'*40 + b'"}', self.archive()]), patch.object(updates.shutil, 'which', return_value='npm.cmd'), \
                     patch.object(updates, 'check', side_effect=ValueError('failed') if failure else None) as check, \
                     patch.dict(updates.JOB, {}, clear=True):
                    updates.prepare()
                    self.assertEqual(updates.JOB['status'], 'failed' if failure else 'ready')
                    candidate = Path(updates.JOB['directory'])
                    self.assertEqual((root/'sample.py').read_text(), 'original')
                    self.assertFalse((candidate/'data').exists())
                    self.assertFalse((candidate/'.env').exists())
                    self.assertEqual((candidate/'ATTIVA.ps1').exists(), not failure)
                    if not failure:
                        self.assertEqual(check.call_count, 4)
                        self.assertEqual(check.call_args.args[2]['CORA_DATABASE_URL'], '')

    def test_server_url_rejects_active_content_and_credentials(self):
        for url in ('javascript:alert(1)', 'http://server/', 'https://user:secret@server/'):
            with patch.dict(os.environ, {'CORA_UPDATE_URL':url}), self.assertRaises(Exception): updates.server_url()

