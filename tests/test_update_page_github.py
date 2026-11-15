import unittest
from unittest.mock import patch

from fastapi import HTTPException

from core import desktop_updates as updates

RELEASE = '12345678-1234-1234-1234-123456789abc'
COMMIT = 'a' * 40


class UpdatePageGitHubTests(unittest.TestCase):
    def setUp(self):
        desktop = patch.object(updates, 'desktop', return_value=False)
        desktop.start(); self.addCleanup(desktop.stop)

    def test_github_comparison_is_read_from_updater(self):
        state = {'configured': True, 'state': 'ahead', 'ahead': 2, 'behind': 0, 'pending': []}
        with patch('programmer_agent.releases.request', return_value=state) as request:
            self.assertEqual(updates.github_server(), {'available': True, **state})
        request.assert_called_once_with('GET', '/host/github', timeout=90)

    def test_older_updater_and_network_failures_are_reported_not_hidden(self):
        with patch('programmer_agent.releases.request', side_effect=ValueError('Operazione non disponibile.')):
            self.assertIn('versione precedente', updates.github_server()['reason'])
        with patch('programmer_agent.releases.request', side_effect=ValueError('Servizio aggiornamenti non disponibile.')):
            value = updates.github_server()
            self.assertFalse(value['available']); self.assertIn('GitHub', value['reason'])

    def test_prepare_is_blocked_while_server_and_github_diverge(self):
        def request(method, path, data=None, **kwargs):
            if path == '/host/github': return {'configured': True, 'state': 'diverged'}
            raise AssertionError('no workspace or job may be created: ' + path)
        with patch('programmer_agent.releases.status', return_value={'available': True}), \
             patch('programmer_agent.releases.request', side_effect=request), \
             patch('programmer_agent.releases.create') as create:
            with self.assertRaises(HTTPException) as error:
                updates.prepare_server()
        self.assertEqual(error.exception.status_code, 409)
        self.assertIn('divergono', error.exception.detail)
        create.assert_not_called()

    def test_publish_submits_only_verified_release_with_expected_commit(self):
        calls = []
        def request(method, path, data=None, **kwargs):
            calls.append((method, path, data))
            if method == 'GET': return {'kind': 'prepare', 'status': 'applied', 'commit': COMMIT}
            return {'id': 'job', 'kind': 'publish'}
        with patch('programmer_agent.releases.request', side_effect=request):
            updates.publish_server(updates.ApplyServerRequest(release_id=RELEASE, expected_commit=COMMIT))
        self.assertEqual(calls[-1], ('POST', '/jobs', {'kind': 'publish', 'release_id': RELEASE, 'commit': COMMIT}))
        for release in ({'kind': 'prepare', 'status': 'failed', 'commit': COMMIT},
                        {'kind': 'prepare', 'status': 'ready', 'commit': 'b' * 40},
                        {'kind': 'apply', 'status': 'completed', 'commit': COMMIT}):
            with patch('programmer_agent.releases.request', return_value=release) as request, \
                 self.assertRaises(HTTPException):
                updates.publish_server(updates.ApplyServerRequest(release_id=RELEASE, expected_commit=COMMIT))
            self.assertEqual(request.call_count, 1)


if __name__ == '__main__':
    unittest.main()
