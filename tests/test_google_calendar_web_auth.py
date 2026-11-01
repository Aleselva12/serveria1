import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from google.auth.exceptions import RefreshError
from core import google_calendar as provider
from core import google_calendar_web_auth as oauth


class CalendarWebAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.token = self.root / 'token.json'
        self.credentials = self.root / 'web-credentials.json'
        self.redirect = 'https://server.example/google-calendar-callback.html'
        self.config = {'web': {'client_id': 'client', 'client_secret': 'test-secret',
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token', 'redirect_uris': [self.redirect]}}
        self.credentials.write_text(json.dumps(self.config))
        self.env = patch.dict(os.environ, {
            'CORA_GOOGLE_CALENDAR_WEB_CREDENTIALS_PATH': str(self.credentials),
            'CORA_GOOGLE_CALENDAR_WEB_REDIRECT_URI': self.redirect})
        self.env.start()
        self.token_patch = patch.object(provider, 'TOKEN_PATH', self.token)
        self.token_patch.start()

    def tearDown(self):
        self.token_patch.stop(); self.env.stop(); self.temp.cleanup()

    def test_missing_setup_or_desktop_client_is_reported_without_secrets(self):
        self.credentials.write_text(json.dumps({'installed': self.config['web']}))
        result = oauth.configuration_status()
        self.assertFalse(result['available'])
        self.assertNotIn('test-secret', str(result))
        with self.assertRaises(oauth.SetupRequired): oauth.start()

    def test_pkce_state_offline_and_private_expiring_session(self):
        result = oauth.start()
        query = parse_qs(urlsplit(result['url']).query)
        self.assertEqual(query['state'], [result['state']])
        self.assertEqual(query['access_type'], ['offline'])
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertNotIn('test-secret', result['url'])
        record_path = self.root / 'oauth-sessions' / (result['state'] + '.json')
        record = json.loads(record_path.read_text())
        self.assertNotEqual(record['key_hash'], result['completion_key'])
        self.assertEqual(record_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(record['verifier']), 86)

    def test_wrong_browser_key_and_path_traversal_cannot_consume_session(self):
        result = oauth.start()
        with self.assertRaises(ValueError): oauth.finish(state=result['state'],completion_key='wrong',code='code')
        with self.assertRaises(ValueError): oauth.finish(state='../token',completion_key='wrong',code='code')
        self.assertTrue((self.root/'oauth-sessions'/(result['state']+'.json')).exists())

    def test_expired_session_is_refused(self):
        result = oauth.start()
        with patch.object(oauth.time,'time',return_value=10**12), self.assertRaises(ValueError):
            oauth.finish(state=result['state'],completion_key=result['completion_key'],code='code')

    def test_cancellation_preserves_existing_account_and_prevents_replay(self):
        self.token.write_text('old working token')
        result = oauth.start()
        self.assertTrue(oauth.finish(state=result['state'],completion_key=result['completion_key'],error='access_denied')['cancelled'])
        self.assertEqual(self.token.read_text(),'old working token')
        with self.assertRaises(ValueError): oauth.finish(state=result['state'],completion_key=result['completion_key'],code='code')

    def test_exchange_and_access_failures_preserve_token_and_redact_errors(self):
        for stage in ('exchange','access'):
            with self.subTest(stage=stage):
                self.token.write_text('old working token')
                result=oauth.start()
                flow=MagicMock();flow.credentials.refresh_token='refresh'
                if stage=='exchange':flow.fetch_token.side_effect=RuntimeError('secret refresh_token=123')
                service=MagicMock()
                if stage=='access': service.events.return_value.list.return_value.execute.side_effect=RuntimeError('secret access')
                with patch.object(oauth.Flow,'from_client_config',return_value=flow), patch.object(oauth,'build',return_value=service):
                    with self.assertRaises(ValueError) as raised:
                        oauth.finish(state=result['state'],completion_key=result['completion_key'],code='auth-code')
                self.assertNotIn('secret',str(raised.exception)); self.assertEqual(self.token.read_text(),'old working token')

    def test_success_verifies_before_private_atomic_save(self):
        result=oauth.start();flow=MagicMock()
        flow.credentials.refresh_token='refresh'
        flow.credentials.to_json.return_value=json.dumps({'refresh_token':'new-token'})
        service=MagicMock()
        with patch.object(oauth.Flow,'from_client_config',return_value=flow), patch.object(oauth,'build',return_value=service):
            outcome=oauth.finish(state=result['state'],completion_key=result['completion_key'],code='auth-code')
        self.assertTrue(outcome['connected'])
        self.assertEqual(json.loads(self.token.read_text())['refresh_token'],'new-token')
        self.assertEqual(self.token.stat().st_mode & 0o777,0o600)
        flow.fetch_token.assert_called_once_with(code='auth-code',timeout=20)
        service.events.return_value.list.return_value.execute.assert_called_once()
        self.assertFalse(list((self.root/'oauth-sessions').iterdir()))

    def test_invalid_refresh_is_visible_as_reconnect_without_secrets(self):
        self.token.write_text('present')
        with patch.object(provider,'service',side_effect=RefreshError('secret invalid_grant')):
            result=provider.status()
        self.assertTrue(result['reauthorizationRequired']);self.assertNotIn('secret',str(result))

    def test_network_error_does_not_claim_reauthorization_is_required(self):
        self.token.write_text('present')
        with patch.object(provider,'service',side_effect=OSError('offline')):
            result=provider.status()
        self.assertFalse(result.get('reauthorizationRequired',False));self.assertFalse(result['reachable'])

    def test_access_token_refresh_remains_automatic(self):
        self.token.write_text('existing');creds=MagicMock();creds.expired=True;creds.refresh_token='valid';creds.valid=True
        with patch.object(provider.Credentials,'from_authorized_user_file',return_value=creds), patch.object(provider,'save_credentials') as save:
            self.assertIs(provider._credentials(),creds)
        creds.refresh.assert_called_once();save.assert_called_once_with(creds)


class CalendarWebAuthApiTests(unittest.TestCase):
    def test_start_and_finish_require_owner_and_hide_setup_details(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from core.calendar_api import router
        app = FastAPI(); app.include_router(router)
        with patch.dict(os.environ, {"CORA_OWNER_TOKEN":"owner"}), TestClient(app) as client:
            for path in ("start", "finish"):
                self.assertEqual(client.post("/api/v1/calendar/google/auth/"+path,json={}).status_code,401)
            with patch.object(oauth, "start", side_effect=OSError("/secret/private.json")):
                response=client.post("/api/v1/calendar/google/auth/start", headers={"Authorization":"Bearer owner"})
            self.assertEqual(response.status_code,409)
            self.assertNotIn("/secret/",response.text)
            with patch.object(oauth,"finish",return_value={"connected":True,"cancelled":False}) as finish:
                response=client.post("/api/v1/calendar/google/auth/finish",json={"state":"state","completion_key":"key","code":"code"},headers={"Authorization":"Bearer owner"})
            self.assertEqual(response.status_code,200);finish.assert_called_once()
