"""Exercise the browser relay against a real local SSH protocol server."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import asyncssh
import httpx2
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from terminal_service.app import Settings, create_app


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.key = asyncssh.generate_private_key('ssh-ed25519')
        self.known = Path(self.temp.name)/'known_hosts'
        self.password_attempts = []
        self.active = set()
        self.config = Settings('owner@example.com', 's'*64, 'https://cora.test.ts.net',
                               '127.0.0.1', 22, 'ale', str(self.known))
        self.headers = {'origin': self.config.origin, 'x-cora-tailscale-login': self.config.owner,
                        'x-cora-proxy-secret': self.config.proxy_secret}
        self.app = create_app(self.config)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        owner = self

        class Server(asyncssh.SSHServer):
            def connection_made(self, conn):
                self.conn = conn
                owner.active.add(conn)

            def connection_lost(self, exc):
                owner.active.discard(self.conn)

            def begin_auth(self, username): return True
            def password_auth_supported(self): return True

            def validate_password(self, username, password):
                owner.password_attempts.append((username, password))
                return username == 'ale' and password == 'correct-password'

        async def shell(process):
            process.stdout.write('Debian test shell\r\n')
            try:
                while data := await process.stdin.read(1024):
                    process.stdout.write('received:' + data)
            except (asyncssh.BreakReceived, asyncssh.TerminalSizeChanged):
                pass
            finally:
                process.exit(0)

        async def start():
            return await asyncssh.create_server(Server, '127.0.0.1', 0,
                server_host_keys=[self.key], process_factory=shell, encoding='utf-8')
        self.server = self.client.portal.call(start)
        # Bind the ephemeral test port before the first request.
        port = self.server.get_port()
        object.__setattr__(self.config, 'port', port)
        self.known.write_text(f'[127.0.0.1]:{port} ' + self.key.export_public_key().decode())

        async def stop():
            self.server.close()
            await self.server.wait_closed()
            for conn in tuple(self.active):
                conn.close()
                await conn.wait_closed()
        self.addCleanup(self.client.portal.call, stop)

    def auth(self, ws, **overrides):
        ws.send_json({'type': 'auth', 'password': 'correct-password', 'cols': 80, 'rows': 24, **overrides})

    def test_status_requires_both_proxy_credential_and_owner(self):
        self.assertEqual(self.client.get('/terminal/status').status_code, 403)
        for key in ('x-cora-proxy-secret', 'x-cora-tailscale-login'):
            headers = dict(self.headers);headers[key] = 'forged'
            self.assertEqual(self.client.get('/terminal/status', headers=headers).status_code, 403)
        response = self.client.get('/terminal/status', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['username'], 'ale')
        self.assertNotIn('proxy_secret', response.text)

    def test_websocket_rejects_missing_foreign_or_duplicate_identity_origin(self):
        cases = [{}, {**self.headers, 'origin': 'https://evil.example'},
                 {k: v for k, v in self.headers.items() if k != 'origin'},
                 {**self.headers, 'x-cora-proxy-secret': 'wrong'}]
        cases.append(httpx2.Headers([*self.headers.items(), ('x-cora-tailscale-login', self.config.owner)]))
        for headers in cases:
            with self.subTest(headers=headers), self.assertRaises(WebSocketDisconnect):
                with self.client.websocket_connect('/terminal/connect', headers=headers): pass
        self.assertEqual(self.password_attempts, [])

    def test_real_ssh_password_pty_input_and_output(self):
        with self.client.websocket_connect('/terminal/connect', headers=self.headers) as ws:
            self.auth(ws)
            self.assertEqual(ws.receive_json(), {'type': 'ready'})
            self.assertIn('Debian test shell', ws.receive_json()['data'])
            ws.send_json({'type': 'input', 'data': 'hello\r'})
            self.assertIn('received:hello', ws.receive_json()['data'])
        self.assertEqual(self.password_attempts, [('ale', 'correct-password')])
        async def closed():
            for _ in range(100):
                if not self.active: return True
                await asyncio.sleep(.01)
            return False
        self.assertTrue(self.client.portal.call(closed))

    def test_bad_password_never_opens_shell_or_leaks_password(self):
        with self.client.websocket_connect('/terminal/connect', headers=self.headers) as ws:
            self.auth(ws, password='sensitive-bad-password')
            message = ws.receive_json()
            self.assertEqual(message['type'], 'error')
            self.assertNotIn('sensitive-bad-password', json.dumps(message))
            with self.assertRaises(WebSocketDisconnect): ws.receive_json()

    def test_changed_host_key_is_rejected_before_password_authentication(self):
        other = asyncssh.generate_private_key('ssh-ed25519')
        self.known.write_text(f'[127.0.0.1]:{self.server.get_port()} ' + other.export_public_key().decode())
        with self.client.websocket_connect('/terminal/connect', headers=self.headers) as ws:
            self.auth(ws)
            self.assertIn('Identità SSH', ws.receive_json()['message'])
        self.assertEqual(self.password_attempts, [])

    def test_browser_cannot_choose_ssh_destination_or_user(self):
        with self.client.websocket_connect('/terminal/connect', headers=self.headers) as ws:
            self.auth(ws, host='other-host', username='root')
            self.assertEqual(ws.receive_json()['type'], 'error')
        self.assertEqual(self.password_attempts, [])

    def test_only_auth_frame_accepted_before_login(self):
        with self.client.websocket_connect('/terminal/connect', headers=self.headers) as ws:
            ws.send_json({'type': 'input', 'data': 'touch /tmp/forbidden\n'})
            self.assertEqual(ws.receive_json()['type'], 'error')
        self.assertEqual(self.password_attempts, [])

    def test_login_rate_limit(self):
        for _ in range(5):
            with self.client.websocket_connect('/terminal/connect', headers=self.headers) as ws:
                self.auth(ws, password='incorrect')
                self.assertEqual(ws.receive_json()['type'], 'error')
                with self.assertRaises(WebSocketDisconnect): ws.receive_json()
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect('/terminal/connect', headers=self.headers): pass
        self.assertEqual(len(self.password_attempts), 5)

    def test_idle_timeout_closes_ssh_even_when_output_exists(self):
        with patch('terminal_service.app.IDLE_SECONDS', 0):
            with self.client.websocket_connect('/terminal/connect', headers=self.headers) as ws:
                self.auth(ws)
                self.assertEqual(ws.receive_json()['type'], 'ready')
                ws.receive_json()
                with self.assertRaises(WebSocketDisconnect) as caught: ws.receive_json()
                self.assertEqual(caught.exception.code, 1000)

    def test_pending_sessions_are_limited_and_slot_is_released(self):
        with self.client.websocket_connect('/terminal/connect', headers=self.headers):
            with self.client.websocket_connect('/terminal/connect', headers=self.headers):
                with self.assertRaises(WebSocketDisconnect):
                    with self.client.websocket_connect('/terminal/connect', headers=self.headers): pass
        with self.client.websocket_connect('/terminal/connect', headers=self.headers) as ws:
            self.auth(ws)
            self.assertEqual(ws.receive_json()['type'], 'ready')

    def test_oversized_frame_closes_connection(self):
        with self.client.websocket_connect('/terminal/connect', headers=self.headers) as ws:
            self.auth(ws)
            self.assertEqual(ws.receive_json()['type'], 'ready')
            ws.receive_json()
            ws.send_json({'type': 'input', 'data': 'x'*17000})
            self.assertEqual(ws.receive_json()['type'], 'error')
            with self.assertRaises(WebSocketDisconnect): ws.receive_json()

    def test_absolute_session_limit(self):
        with patch('terminal_service.app.MAX_SECONDS', 0):
            with self.client.websocket_connect('/terminal/connect', headers=self.headers) as ws:
                self.auth(ws)
                self.assertEqual(ws.receive_json()['type'], 'ready')
                ws.receive_json()
                with self.assertRaises(WebSocketDisconnect): ws.receive_json()

    def test_no_shell_and_no_credentials_without_config(self):
        with patch.dict('os.environ', {}, clear=True):
            with TestClient(create_app()) as client:
                self.assertEqual(client.get('/terminal/status').status_code, 503)


class SetupTests(unittest.TestCase):
    def test_local_public_host_key_only(self):
        from deploy.terminal_setup import known_host_line
        self.assertEqual(known_host_line('ssh-ed25519 AAAABBBB host\n'), 'host.docker.internal ssh-ed25519 AAAABBBB\n')
        for value in ('', 'ssh-rsa AAAA', 'ssh-ed25519 bad;command'):
            with self.assertRaises(ValueError): known_host_line(value)
