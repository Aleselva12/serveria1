import hashlib
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from core import auth, ollama_transport
from updater.engine import Engine


class AuditClosureTests(unittest.TestCase):
    def make_symlink(self, link, target, **kwargs):
        try:
            link.symlink_to(target, **kwargs)
        except OSError as error:
            if os.name == "nt" and (getattr(error, "winerror", None) == 1314 or error.errno in {1, 13}):
                self.skipTest("Windows requires Developer Mode or symlink privileges for this test")
            raise

    def test_proxy_identity_requires_trusted_peer_and_single_ip(self):
        def request(peer, forwarded):
            return SimpleNamespace(client=SimpleNamespace(host=peer), headers={'x-forwarded-for': forwarded})
        with patch.dict(os.environ, {'CORA_TRUSTED_PROXY_HOSTS': '172.18.0.3'}):
            self.assertEqual(auth.client_address(request('172.18.0.3', '100.80.1.2')), '100.80.1.2')
            self.assertEqual(auth.client_address(request('172.18.0.4', '100.80.1.2')), '172.18.0.4')
            self.assertEqual(auth.client_address(request('172.18.0.3', '1.2.3.4, 5.6.7.8')), '172.18.0.3')
        with patch.dict(os.environ, {'CORA_TRUSTED_PROXY_HOSTS': 'web'}), patch('socket.getaddrinfo', return_value=[(None,None,None,None,('172.18.0.3',80))]):
            self.assertEqual(auth.client_address(request('172.18.0.3', '100.80.1.3')), '100.80.1.3')

    def test_login_throttle_is_separate_for_two_forwarded_clients(self):
        from fastapi import HTTPException, Response
        def request(ip):
            return SimpleNamespace(client=SimpleNamespace(host='172.18.0.3'), headers={'x-forwarded-for':ip})
        with patch.dict(os.environ, {'CORA_TRUSTED_PROXY_HOSTS':'172.18.0.3'}), patch.object(auth, '_attempts', {}), patch.object(auth, 'db_connection') as db:
            db.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = None
            credentials = auth.Login(username='owner', password='incorrect')
            for _ in range(5):
                with self.assertRaises(HTTPException) as error: auth.login(credentials, request('100.80.1.2'), Response())
                self.assertEqual(error.exception.status_code, 401)
            with self.assertRaises(HTTPException) as error: auth.login(credentials, request('100.80.1.2'), Response())
            self.assertEqual(error.exception.status_code, 429)
            with self.assertRaises(HTTPException) as error: auth.login(credentials, request('100.80.1.3'), Response())
            self.assertEqual(error.exception.status_code, 401)

    def test_ollama_endpoint_and_transport_ignore_environment_proxy(self):
        with patch.dict(os.environ, {'OLLAMA_BASE_URL':'', 'HTTP_PROXY':'http://invalid-proxy:123'}):
            self.assertEqual(ollama_transport.get_ollama_base_url(), 'http://localhost:11434')
            with patch.object(ollama_transport, 'build_opener') as opener:
                ollama_transport.urlopen('http://localhost:11434/api/tags', timeout=1)
                self.assertEqual(opener.call_args.args[0].proxies, {})
        with patch.dict(os.environ, {'OLLAMA_BASE_URL':' http://ollama:11434/ '}):
            self.assertEqual(ollama_transport.get_ollama_base_url(), 'http://ollama:11434')

    def test_model_selection_distinguishes_disk_failure_and_uses_single_probe(self):
        import api
        from core.models import RuntimeSettingsError
        from fastapi import HTTPException
        models = [{'name':'new'}]
        with patch.object(api,'list_ollama_models',return_value=models) as listing, patch.object(api,'save_runtime_model',side_effect=RuntimeSettingsError('Impossibile salvare il modello.')):
            with self.assertRaises(HTTPException) as error: api.select_runtime_model(api.ModelSelectionRequest(model='new'))
            self.assertEqual(error.exception.status_code,500)
            listing.assert_called_once()
        with patch.object(api,'list_ollama_models',return_value=models) as listing, patch.object(api,'save_runtime_model'), patch.object(api,'get_model_name',return_value='new'):
            self.assertEqual(api.select_runtime_model(api.ModelSelectionRequest(model='new')),{'active':'new','models':models})
            listing.assert_called_once()

    def test_host_check_copies_validated_workspace_and_rejects_changed_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); state=root/'state'; state.mkdir()
            (root/'config.json').write_text(json.dumps({'state_root':str(state)}))
            engine=Engine(root); key=str(uuid4()); path=engine.workspaces/key
            (path/'files/tests').mkdir(parents=True)
            (path/'manifest.json').write_text('{}')
            content='import unittest\n';(path/'files/tests/test_one.py').write_text(content)
            digest=hashlib.sha256(json.dumps([('tests/test_one.py',hashlib.sha256(content.encode()).hexdigest())]).encode()).hexdigest()
            def run(snapshot, paths, profile):
                self.assertFalse(snapshot.is_relative_to(state))
                self.assertEqual((snapshot/'tests/test_one.py').read_text(),content)
                self.assertEqual(paths,['tests/test_one.py'])
                self.assertEqual(profile,'python_tests')
                self.assertEqual((snapshot/'tests').stat().st_mode & 0o777,0o755)
                return {'passed':True}
            with patch('updater.check_runner.run',side_effect=run) as runner:
                previous_umask=os.umask(0o077)
                try:
                    self.assertTrue(engine.check_workspace(key,'python_tests',digest)['passed'])
                finally:
                    os.umask(previous_umask)
                with self.assertRaises(ValueError): engine.check_workspace(key,'python_tests','0'*64)
                with self.assertRaises(ValueError): engine.check_workspace(key,'shell',digest)
                self.make_symlink(path / 'files/unsafe.py', path / 'manifest.json')
                with self.assertRaises(ValueError): engine.check_workspace(key,'python_tests',digest)
                runner.assert_called_once()
            self.assertEqual(list(root.glob('check-*')),[])

    def test_backend_uses_host_bridge_without_docker_cli(self):
        from programmer_agent.checks import docker_check
        with patch.dict(os.environ, {'CORA_UPDATER_URL':'http://host:9021'}), patch('programmer_agent.components.workspace_digest',return_value='a'*64), patch('programmer_agent.releases.request',return_value={'passed':True}) as request, patch('programmer_agent.checks.shutil.which',return_value=None):
            self.assertTrue(docker_check('workspace-id')['passed'])
            request.assert_called_once_with('POST','/workspaces/workspace-id/check',{'profile':'python_tests','workspace_digest':'a'*64},timeout=180)

    def test_windows_long_path_has_client_error(self):
        from core.server_files import guard
        from fastapi import HTTPException
        error = OSError(22, 'invalid path'); error.winerror = 206
        with self.assertRaises(HTTPException) as caught:
            with guard(): raise error
        self.assertEqual(caught.exception.status_code,400)

    def test_host_http_check_requires_token_and_exact_payload(self):
        from http.server import ThreadingHTTPServer
        from updater.service import handler
        import httpx
        engine=MagicMock()
        engine.check_workspace.return_value={'passed':True,'environment':'docker-host'}
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(engine,'private-token'))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}',trust_env=False) as client:
                data={'profile':'python_tests','workspace_digest':'a'*64}
                self.assertEqual(client.post('/workspaces/id/check',json=data).status_code,401)
                engine.check_workspace.assert_not_called()
                client.headers['Authorization']='Bearer private-token'
                self.assertEqual(client.post('/workspaces/id/check',json={**data,'command':'whoami'}).status_code,404)
                engine.check_workspace.assert_not_called()
                response=client.post('/workspaces/id/check',json=data)
                self.assertEqual(response.status_code,200)
                self.assertTrue(response.json()['passed'])
                engine.check_workspace.assert_called_once_with('id','python_tests','a'*64)
        finally:
            server.shutdown();server.server_close();thread.join()
