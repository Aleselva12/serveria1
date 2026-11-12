"""The updater keeps every host part on the release it installs.

* before an apply, the updater switches to the package shipped with the release;
* the optional terminal is rebuilt and switched with api/web;
* /host/components reports any part that is not on the active release.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from updater import components, maintenance
from updater.engine import DB_IMPORT, Engine, atomic


def git(*args, cwd):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


@unittest.skipUnless(os.name == 'posix' and shutil.which('git'), 'Requires Linux host and Git')
class SelfUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name); project = base/'project'; project.mkdir()
        git('init', '-q', str(project), cwd=base)
        for name, content in {'app.py': 'value=1\n', 'compose.yml': 'services: {}\n',
                              'updater/service.py': 'VERSION = 1\n', 'tests/test_example.py': 'import unittest\n'}.items():
            path = project/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
        git('add', '.', cwd=project)
        git('-c', 'user.name=Test', '-c', 'user.email=test@localhost', 'commit', '-qm', 'Initial', cwd=project)
        self.base_commit = git('rev-parse', 'HEAD', cwd=project)
        root = base/'control'; root.mkdir(); state = base/'state'; state.mkdir()
        subprocess.run(['git', 'clone', '-q', '--bare', str(project), str(root/'repo.git')], check=True)
        atomic(root/'config.json', {'state_root': str(state), 'project': 'cora-test', 'uid': os.getuid(), 'gid': os.getgid(),
                                    'api_target': 'api', 'listen': '127.0.0.1', 'port': 0})
        atomic(root/'current.json', {'commit': self.base_commit, 'images': {'api': 'sha256:old-api', 'web': 'sha256:old-web'}})
        atomic(root/'compose.json', {'services': {'api': {}, 'web': {}, 'postgres': {}}})
        (root/'maintenance.enabled').touch()
        self.root = root
        self.engine = Engine(root)
        self.engine.apps = SimpleNamespace(lock=threading.Lock())
        workspace = self.engine.create_workspace('Release with a new updater')
        files = state/'programmer'/workspace['id']/'files'
        (files/'updater/service.py').write_text('VERSION = 2\n')
        commit = self.engine.commit_workspace(workspace['id'], 'New updater')['commit']
        release = self.engine.load(self.engine.submit('prepare', workspace['id'], commit)['id'])
        release.update(status='ready', images={'api': 'sha256:new-api', 'web': 'sha256:new-web'}); self.engine.save(release)
        self.release = release
        self.job = self.engine.load(self.engine.submit('apply', commit=commit, release_id=release['id'])['id'])
        self.candidate_digest = maintenance.commit_digest(self.engine.repo, commit)

    def run_apply(self, installed):
        calls = []
        with patch('updater.maintenance.installed_digest', return_value=installed), \
             patch.object(self.engine, 'images', return_value={'api': 'sha256:old-api', 'web': 'sha256:old-web'}), \
             patch.object(self.engine, 'backup', side_effect=lambda row: calls.append('backup')), \
             patch.object(self.engine, 'migration_trial', side_effect=lambda row, image: calls.append('trial')), \
             patch.object(self.engine, 'compose', side_effect=lambda *a, **k: calls.append(a[0]) or ''):
            self.engine.execute(self.engine.load(self.job['id']))
        return calls, self.engine.load(self.job['id'])

    def test_apply_hands_off_to_candidate_updater_before_touching_cora(self):
        calls, row = self.run_apply('0'*64)
        self.assertEqual(calls, [])  # nothing stopped, backed up or started
        self.assertEqual((row['status'], row['phase'], row['updater_handoff']), ('queued', 'awaiting_updater', 'requested'))
        request = __import__('json').loads((self.root/'maintenance.request').read_text())
        self.assertEqual(request, {'commit': self.release['commit'], 'digest': self.candidate_digest, 'handoff_job': row['id']})
        self.assertEqual((self.root/'maintenance.next/updater/service.py').read_text(), 'VERSION = 2\n')
        # The bridge accepts no new job while the switch is pending.
        with self.assertRaises(ValueError):
            self.engine.submit('apply', commit=self.release['commit'], release_id=self.release['id'])

    def test_resumed_job_installs_with_the_new_updater(self):
        self.run_apply('0'*64)
        (self.root/'maintenance.request').unlink()  # helper finished the switch
        calls, row = self.run_apply(self.candidate_digest)
        self.assertEqual(calls[:2], ['backup', 'trial'])
        self.assertEqual((row['status'], row['updater_handoff']), ('completed', 'switched'))
        self.assertEqual(self.engine.current()['commit'], self.release['commit'])

    def test_helper_rollback_does_not_loop(self):
        self.run_apply('0'*64)
        (self.root/'maintenance.request').unlink()  # helper restored the old package
        calls, row = self.run_apply('0'*64)
        self.assertIn('backup', calls)
        self.assertEqual((row['status'], row['updater_handoff']), ('completed', 'kept_previous'))
        self.assertFalse((self.root/'maintenance.request').exists())

    def test_aligned_updater_installs_directly(self):
        calls, row = self.run_apply(self.candidate_digest)
        self.assertEqual(row['updater_handoff'], 'aligned')
        self.assertEqual(row['status'], 'completed')

    def test_busy_apps_skip_handoff_and_still_install(self):
        self.engine.apps.lock.acquire()
        self.addCleanup(self.engine.apps.lock.release)
        calls, row = self.run_apply('0'*64)
        self.assertTrue(row['updater_handoff'].startswith('skipped'))
        self.assertEqual(row['status'], 'completed')

    def test_owner_alignment_still_refuses_a_non_active_commit(self):
        with patch('updater.maintenance.installed_digest', return_value='0'*64), self.assertRaises(ValueError):
            maintenance.submit(self.engine, self.engine.apps, self.release['commit'], self.candidate_digest)

    def test_handoff_refuses_jobs_that_are_not_applies_of_ready_releases(self):
        with patch('updater.maintenance.installed_digest', return_value='0'*64), self.assertRaises(ValueError):
            maintenance.handoff(self.engine, self.engine.apps, self.release['id'], self.release['commit'], self.candidate_digest)

    def test_worker_waits_for_pending_switch(self):
        atomic(self.root/'maintenance.request', {'commit': self.release['commit'], 'digest': self.candidate_digest})
        with patch.object(self.engine, 'execute') as execute, patch('updater.data_backups.recover_pending'), \
             patch('updater.data_backups.tick'):
            self.engine.start()
            self.engine.worker.join(1.5)
            self.engine.closed.set(); self.engine.wakeup.set(); self.engine.worker.join(3)
        execute.assert_not_called()

    def test_terminal_is_built_and_switched_with_the_release(self):
        atomic(self.root/'compose.json', {'services': {'api': {}, 'web': {}, 'terminal': {}}})
        self.assertEqual(self.engine.release_services(), ['api', 'web', 'terminal'])
        calls = []
        with patch.object(self.engine, 'compose', side_effect=lambda *a, **k: calls.append(a) or ''):
            self.engine.up({'api': 'a', 'web': 'w', 'terminal': 't'})
            self.engine.up({'api': 'a', 'web': 'w'})  # rollback to a release built before the terminal
        self.assertEqual(calls[0][-3:], ('api', 'web', 'terminal'))
        self.assertEqual(calls[1][-2:], ('api', 'web'))
        built = []
        def command(args, **kwargs):
            if args[0] != 'docker':
                return Engine.cmd(self.engine, args, **kwargs)
            if args[1] == 'build':
                built.append(args[args.index('--target')+1])
            if args[1:3] == ['image', 'inspect']:
                return 'sha256:' + 'a'*64
            if args[1] == 'run':
                return 'Ran 3 tests in 0.1s\nOK'
            return ''
        prepare = self.engine.load(self.release['id']); prepare.update(status='queued'); prepare.pop('images')
        with patch.object(self.engine, 'cmd', side_effect=command):
            self.engine.build(prepare)
        self.assertEqual(built, ['api', 'web', 'terminal'])
        self.assertEqual(sorted(self.engine.load(prepare['id'])['images']), ['api', 'terminal', 'web'])

    def test_components_report_every_stale_part(self):
        atomic(self.root/'compose.json', {'services': {'api': {}, 'web': {}, 'terminal': {}}})
        running = {'api': 'sha256:old-api', 'web': 'sha256:other', 'terminal': 'sha256:manual'}
        helper = self.root/'helper.py'
        reference = git('--git-dir', str(self.engine.repo), 'show', self.base_commit+':updater/service.py', cwd=self.root)
        helper.write_text(reference + '\n')
        with patch.object(self.engine, 'running_image', side_effect=running.get), \
             patch('updater.maintenance.installed_digest', return_value='0'*64), \
             patch('updater.maintenance.commit_digest', return_value='f'*64), \
             patch('updater.components.subprocess.check_output', return_value=reference.encode()), \
             patch('updater.components.HELPER', helper):
            components._cache.update(value=None)
            result = components.inspect(self.engine)
        status = {row['id']: row['status'] for row in result['components']}
        self.assertEqual(status, {'api': 'ok', 'web': 'outdated', 'terminal': 'untracked',
                                  'updater': 'outdated', 'helper': 'ok'})
        self.assertFalse(result['aligned'])


class HelperShapeTests(unittest.TestCase):
    def test_import_order_and_formatting_do_not_count_as_a_new_version(self):
        a = b'import os\nfrom pathlib import Path\n\ndef f():\n    return 1\n'
        b = b'from pathlib import Path\nimport os\n\n\ndef f():  # comment\n    return 1\n'
        self.assertEqual(components._shape(a), components._shape(b))
        self.assertNotEqual(components._shape(a), components._shape(a.replace(b'1', b'2')))


class DatabaseProbeTests(unittest.TestCase):
    def probe(self, modules):
        saved = {name: sys.modules.get(name) for name in ('core', 'core.infra', 'core.infra.database', 'core.database')}
        try:
            for name in saved:
                sys.modules.pop(name, None)
            for name, value in modules.items():
                sys.modules[name] = value
            scope = {}
            exec(DB_IMPORT, scope)  # noqa: S102 - fixed probe text, same as the updater runs
            return scope['db_connection']
        finally:
            for name, value in saved.items():
                if value is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value

    def module(self, name, marker):
        value = types.ModuleType(name); value.db_connection = marker; return value

    def test_new_layout(self):
        core = types.ModuleType('core'); core.__path__ = []
        infra = types.ModuleType('core.infra'); infra.__path__ = []
        self.assertEqual(self.probe({'core': core, 'core.infra': infra,
                                     'core.infra.database': self.module('core.infra.database', 'new')}), 'new')

    def test_old_layout(self):
        core = types.ModuleType('core'); core.__path__ = []
        self.assertEqual(self.probe({'core': core, 'core.database': self.module('core.database', 'old')}), 'old')


class StatusEndpointTests(unittest.TestCase):
    def test_server_status_carries_component_versions_or_says_they_are_missing(self):
        from core import desktop_updates
        status = {'available': True, 'active_commit': 'a'*40, 'jobs': []}
        report = {'commit': 'a'*40, 'aligned': True, 'components': []}
        def request(method, path, *args, **kwargs):
            if path == '/host/components':
                return report
            raise AssertionError(path)
        with patch.object(desktop_updates, 'desktop', return_value=False), \
             patch('programmer_agent.releases.status', return_value=status), \
             patch('programmer_agent.releases.request', side_effect=request):
            self.assertEqual(desktop_updates.status()['components'], report)
        with patch.object(desktop_updates, 'desktop', return_value=False), \
             patch('programmer_agent.releases.status', return_value=status), \
             patch('programmer_agent.releases.request', side_effect=ValueError('404')):
            self.assertIsNone(desktop_updates.status()['components'])


if __name__ == '__main__':
    unittest.main()
