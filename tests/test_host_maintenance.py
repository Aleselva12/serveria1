import json
from pathlib import Path
import tempfile
import unittest
from updater.host_maintenance import execute, write
from updater.maintenance import digest

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for name,content in [('installed','old'),('maintenance.next','new')]:
            (self.root/name).mkdir();(self.root/name/'version').write_text(content)
        write(self.root/'maintenance.request',{'commit':'a'*40,'digest':'b'*64})
        self.calls=[]
    def result(self): return json.loads((self.root/'maintenance.result.json').read_text())['status']
    def test_success_keeps_previous(self):
        execute(self.root,self.calls.append,lambda *args:True)
        self.assertEqual(self.result(),'completed')
        self.assertEqual((self.root/'installed/version').read_text(),'new')
        self.assertEqual((self.root/'maintenance.previous/version').read_text(),'old')
        self.assertFalse((self.root/'maintenance.request').exists())
    def test_bad_candidate_restores_previous(self):
        execute(self.root,self.calls.append,lambda root,expected=None:expected is None)
        self.assertEqual(self.result(),'rolled_back')
        self.assertEqual((self.root/'installed/version').read_text(),'old')
    def test_failed_recovery_stays_blocked(self):
        with self.assertRaises(RuntimeError): execute(self.root,self.calls.append,lambda *args:False)
        self.assertEqual(self.result(),'recovery_required')
        self.assertTrue((self.root/'maintenance.request').exists())
    def test_interrupted_switch_restores_previous(self):
        (self.root/'installed').rename(self.root/'maintenance.previous')
        write(self.root/'maintenance.journal.json',{'commit':'a'*40,'digest':'b'*64,'phase':'switching'})
        execute(self.root,self.calls.append,lambda *args:True)
        self.assertEqual(self.result(),'rolled_back')
        self.assertEqual((self.root/'installed/version').read_text(),'old')
    def test_digest_changes_with_source(self):
        file=self.root/'test.py';file.write_text('x=1\n');first=digest(self.root)
        file.write_text('x=2\n');self.assertNotEqual(first,digest(self.root))

class PrerequisiteTests(unittest.TestCase):
    def test_compatible_does_not_post(self):
        from unittest.mock import patch
        from core.host_maintenance import ensure
        with patch.dict('os.environ',{'CORA_UPDATER_URL':'http://host'}), patch('core.host_maintenance.digest',return_value='b'*64), patch('programmer_agent.releases.request',return_value={'digest':'b'*64,'pending':False}) as call:
            self.assertEqual(ensure()['status'],'compatible')
            call.assert_called_once_with('GET','/host/maintenance',timeout=5)
    def test_missing_bootstrap_never_updates(self):
        from unittest.mock import patch
        from core.host_maintenance import ensure
        with patch.dict('os.environ',{'CORA_UPDATER_URL':'http://host'}), patch('programmer_agent.releases.request',return_value={'available':False}) as call:
            with self.assertRaises(ValueError): ensure()
            self.assertEqual(call.call_count,1)

class CandidateTests(unittest.TestCase):
    def test_exact_git_bytes_and_busy_jobs(self):
        from types import SimpleNamespace
        from threading import RLock, Lock
        import subprocess
        from updater.maintenance import submit
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);repo=root/'source';repo.mkdir();(repo/'updater').mkdir()
            (repo/'updater/service.py').write_text('x = 1\n\n')
            subprocess.run(['git','init','-q',str(repo)],check=True)
            subprocess.run(['git','-C',str(repo),'add','.'],check=True)
            subprocess.run(['git','-C',str(repo),'-c','user.name=Test','-c','user.email=test@example.org','commit','-qm','fixture'],check=True)
            commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
            (root/'maintenance.enabled').touch()
            engine=SimpleNamespace(root=root,repo=repo/'.git',lock=RLock(),current=lambda:{'commit':commit},list_jobs=lambda:[])
            apps=SimpleNamespace(lock=Lock())
            result=submit(engine,apps,commit,digest(repo/'updater'))
            self.assertEqual(result['status'],'queued')
            self.assertEqual((root/'maintenance.next/updater/service.py').read_bytes(),b'x = 1\n\n')
            with self.assertRaises(ValueError):submit(engine,apps,commit,result['digest'])
            (root/'maintenance.request').unlink()
            engine.list_jobs=lambda:[{'status':'running'}]
            with self.assertRaises(ValueError):submit(engine,apps,commit,result['digest'])

class BootstrapTests(unittest.TestCase):
    def test_failed_health_restores_original_and_removes_new_units(self):
        from unittest.mock import patch
        from contextlib import ExitStack
        from types import SimpleNamespace
        import os
        from updater import install_maintenance as installer
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            base=Path(temporary); root=base/'root';root.mkdir();(root/'jobs').mkdir()
            (root/'installed').mkdir();(root/'installed/old').write_text('original')
            units=base/'units';units.mkdir()
            helper=base/'helper.py';policy=base/'policy'
            def run(*args):
                if '-p' in args:
                    return 'ale' if 'User' in args else str(root/'installed')
                return ''
            for key,value in {'ROOT':root,'HELPER':helper,'POLICY':policy,'UNITS':units}.items():
                stack.enter_context(patch.object(installer,key,value))
            stack.enter_context(patch.object(installer,'run',side_effect=run))
            stack.enter_context(patch.object(installer.os,'geteuid',return_value=0))
            stack.enter_context(patch.object(installer.pwd,'getpwnam',return_value=SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid())))
            stack.enter_context(patch('updater.host_maintenance.healthy',return_value=False))
            stack.enter_context(patch.object(installer.subprocess,'run'))
            with self.assertRaisesRegex(RuntimeError,'Health bootstrap'):installer.main()
            self.assertEqual((root/'installed/old').read_text(),'original')
            self.assertFalse(helper.exists());self.assertFalse(policy.exists())
            self.assertEqual(list(units.iterdir()),[])
            self.assertFalse((root/'maintenance.enabled').exists())
