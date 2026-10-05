import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import httpx
from updater.engine import Engine, atomic
from updater.service import handler


@unittest.skipUnless(os.name == "posix" and shutil.which("git"), "Requires Linux host and Git")
class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name);project=base/'project';project.mkdir()
        subprocess.run(['git','init','-q',str(project)],check=True)
        for name,content in {'.gitignore':'.env\n', '.dockerignore':'.git\n', 'app.py':'value=1\n', 'compose.yml':'services: {}\n', 'Dockerfile':'FROM python:3.12-slim AS api\n', 'tests/test_example.py':'import unittest\n'}.items():
            path=project/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
        (project/'.env').write_text('PRIVATE=hidden')
        subprocess.run(['git','add','.'],cwd=project,check=True)
        subprocess.run(['git','-c','user.name=Test','-c','user.email=test@localhost','commit','-qm','Initial'],cwd=project,check=True)
        self.base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=project,text=True).strip()
        root=base/'control';root.mkdir();state=base/'state';state.mkdir()
        subprocess.run(['git','clone','-q','--bare',str(project),str(root/'repo.git')],check=True)
        atomic(root/'config.json',{'state_root':str(state),'project':'cora-test','uid':os.getuid(),'gid':os.getgid(),'api_target':'api','listen':'127.0.0.1','port':0})
        atomic(root/'current.json',{'commit':self.base_commit});atomic(root/'compose.json',{'services':{}})
        self.engine=Engine(root);self.workspace=self.engine.create_workspace('Requested update')
        self.files=state/'programmer'/self.workspace['id']/'files'

    def change(self):
        (self.files/'app.py').write_text('value=2\n')
        return self.engine.commit_workspace(self.workspace['id'],'Requested change')['commit']

    def ready(self):
        commit=self.change();row=self.engine.submit('prepare',self.workspace['id'],commit)
        full=self.engine.load(row['id']);full.update(status='ready',images={'api':'sha256:new-api','web':'sha256:new-web'});self.engine.save(full)
        return full

    def test_failed_setup_restores_existing_deployment_configuration(self):
        from updater.setup import initialize
        project=Path(self.temp.name)/'project'
        deploy=project/'deploy.env'
        original='CORA_STATE_ROOT='+str(self.engine.state)+'\nCORA_UID='+str(os.getuid())+'\n'
        deploy.write_text(original);deploy.chmod(0o640)
        root=Path(self.temp.name)/'failed-control'
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=project,text=True)
        with patch('updater.setup.subprocess.check_output',side_effect=[revision,RuntimeError('Docker unavailable')]):
            with self.assertRaises(RuntimeError):initialize(root,project,'HEAD',listen='127.0.0.1')
        self.assertFalse(root.exists())
        self.assertEqual(deploy.read_text(),original)
        self.assertEqual(deploy.stat().st_mode & 0o777,0o640)

    def test_git_workspace_is_full_and_commit_forces_ignored_sources_without_secrets(self):
        self.assertTrue((self.files/'.dockerignore').is_file())
        self.assertFalse((self.files/'.env').exists())
        (self.files/'.gitignore').write_text('generated.py\n')
        (self.files/'generated.py').write_text('value=42\n')
        commit=self.engine.commit_workspace(self.workspace['id'],'Add tool')['commit']
        self.assertEqual(self.engine.git('show',commit+':generated.py'),'value=42')
        job=self.engine.submit('prepare',self.workspace['id'],commit)
        self.assertEqual(job['status'],'queued')
        self.assertEqual(job['base_commit'],self.base_commit)
        with self.assertRaises(ValueError):self.engine.submit('prepare',self.workspace['id'],commit)

    def test_dirty_workspace_or_changed_active_version_cannot_release(self):
        commit=self.change();(self.files/'app.py').write_text('value=3\n')
        with self.assertRaises(ValueError):self.engine.submit('prepare',self.workspace['id'],commit)
        ready=self.ready();atomic(self.engine.root/'current.json',{'commit':'f'*40})
        with self.assertRaises(ValueError):self.engine.submit('apply',commit=ready['commit'],release_id=ready['id'])

    def test_build_uses_exact_git_commit_and_isolated_test_runner(self):
        commit=self.change();job=self.engine.submit('prepare',self.workspace['id'],commit);row=self.engine.load(job['id'])
        original=self.engine.cmd;calls=[]
        def command(args,**kwargs):
            if args[0]!='docker':return original(args,**kwargs)
            calls.append(args)
            if args[1:3]==['image','inspect']:return 'sha256:'+'a'*64
            if args[1]=='run':return 'Ran 3 tests in 0.1s\nOK (skipped=1)'
            return ''
        with patch.object(self.engine,'cmd',side_effect=command):self.engine.execute(row)
        result=self.engine.load(job['id']);self.assertEqual(result['status'],'ready')
        self.assertEqual((self.engine.path(job['id'])/'source'/'app.py').read_text(),'value=2\n')
        run=next(c for c in calls if c[1]=='run')
        for flag in ('--network=none','--read-only','--cap-drop=ALL'):self.assertIn(flag,run)
        self.assertEqual(self.engine.current()['commit'],self.base_commit)

    def test_migration_copy_waits_for_final_tcp_server_before_restoring(self):
        ready=self.ready()
        job=self.engine.submit('apply',commit=ready['commit'],release_id=ready['id'])
        row=self.engine.load(job['id'])
        backup=self.engine.path(row['id'])/'backup';backup.mkdir()
        (backup/'database.dump').write_bytes(b'database copy')
        events=[];attempts=0
        def command(args, **kwargs):
            nonlocal attempts
            if 'pg_isready' in args:
                # The socket-only initialization server is already up, but TCP isn't.
                if '-h' not in args: return ''
                self.assertEqual(args[args.index('-h')+1], '127.0.0.1')
                attempts+=1
                if attempts==1:
                    events.append('initializing')
                    raise RuntimeError('TCP not ready')
                events.append('ready')
            elif 'pg_restore' in args:
                events.append('restore')
                self.assertEqual(kwargs['stdin'].read(), b'database copy')
                self.assertEqual(args[args.index('-h')+1], '127.0.0.1')
            elif '--entrypoint=python' in args: events.append('migrate')
            return 'sha256:postgres' if 'inspect' in args else ''
        with patch.object(self.engine,'compose',return_value='postgres-container'), patch.object(self.engine,'cmd',side_effect=command), patch('time.sleep'):
            self.engine.migration_trial(row,ready['images']['api'])
        self.assertEqual(events,['initializing','ready','restore','migrate'])
        self.assertTrue(row['checks']['migration_copy'])

    def test_failed_activation_recovers_previous_images_and_data(self):
        ready=self.ready();public=self.engine.submit('apply',commit=ready['commit'],release_id=ready['id']);row=self.engine.load(public['id'])
        previous={'api':'sha256:old-api','web':'sha256:old-web'};restores=[]
        def backup(r):r['backup_valid']=True;self.engine.phase(r,'backup_complete')
        def compose(*args,**kwargs):
            if kwargs.get('images')==ready['images']:raise RuntimeError('Candidate failed')
            return ''
        def restore(r,backup_id,images,commit):restores.append((backup_id,images,commit));r['rollback']='restored';self.engine.save(r)
        with patch.object(self.engine,'images',return_value=previous),patch.object(self.engine,'backup',side_effect=backup),patch.object(self.engine,'migration_trial'),patch.object(self.engine,'compose',side_effect=compose),patch.object(self.engine,'restore',side_effect=restore):self.engine.execute(row)
        self.assertEqual(restores,[(row['id'],previous,self.base_commit)])
        self.assertEqual(self.engine.load(row['id'])['status'],'failed')
        self.assertEqual(self.engine.load(row['id'])['rollback'],'restored')

    def test_recovery_failure_blocks_subsequent_releases(self):
        ready=self.ready();job=self.engine.submit('apply',commit=ready['commit'],release_id=ready['id']);row=self.engine.load(job['id'])
        row.update(previous_commit=self.base_commit,previous_images={'api':'old','web':'old'},backup_valid=True,phase='candidate_starting')
        with patch.object(self.engine,'apply',side_effect=RuntimeError('Failure')),patch.object(self.engine,'recover',side_effect=RuntimeError('Recovery failed')):self.engine.execute(row)
        self.assertEqual(self.engine.load(job['id'])['status'],'recovery_required')
        with self.assertRaises(ValueError):self.engine.submit('apply',commit=ready['commit'],release_id=ready['id'])

    def test_manual_rollback_preserves_new_data_backup_before_restoring_old(self):
        ready=self.ready();original=self.engine.submit('apply',commit=ready['commit'],release_id=ready['id']);apply_row=self.engine.load(original['id'])
        old={'api':'old-api','web':'old-web'};new=ready['images']
        apply_row.update(status='completed',previous_images=old,previous_commit=self.base_commit,backup_valid=True);self.engine.save(apply_row)
        ready.update(status='applied',applied_job=original['id']);self.engine.save(ready)
        atomic(self.engine.root/'current.json',{'commit':ready['commit']})
        requested=self.engine.submit('rollback',commit=ready['commit'],release_id=ready['id']);row=self.engine.load(requested['id']);events=[]
        def backup(r):events.append(('backup',r['id']))
        def restore(r,key,images,commit):events.append(('restore',key,images,commit))
        with patch.object(self.engine,'images',return_value=new),patch.object(self.engine,'backup',side_effect=backup),patch.object(self.engine,'restore',side_effect=restore):self.engine.execute(row)
        self.assertEqual(events,[('backup',row['id']),('restore',original['id'],old,self.base_commit)])
        self.assertEqual(self.engine.load(row['id'])['status'],'completed')

    def test_private_service_requires_token_and_returns_no_secrets(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.engine,'private-token'))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with httpx.Client(base_url='http://127.0.0.1:'+str(server.server_port),trust_env=False) as client:
                self.assertEqual(client.get('/status').status_code,401)
                response=client.get('/status',headers={'Authorization':'Bearer private-token'})
                self.assertEqual(response.status_code,200)
                self.assertNotIn('private-token',response.text)
                self.assertEqual(response.json()['active_commit'],self.base_commit)
        finally:server.shutdown();server.server_close();thread.join()

    def test_restore_validates_archive_before_destructive_commands(self):
        import tarfile,io
        from updater.engine import file_digest
        ready=self.ready();job=self.engine.submit('apply',commit=ready['commit'],release_id=ready['id']);row=self.engine.load(job['id'])
        backup=self.engine.path(row['id'])/'backup';backup.mkdir();(backup/'database.dump').write_bytes(b'fake dump')
        with tarfile.open(backup/'state.tar.gz','w:gz') as archive:
            member=tarfile.TarInfo('state/external');member.type=tarfile.SYMTYPE;member.linkname='/outside';archive.addfile(member)
        atomic(backup/'manifest.json',{p.name:file_digest(p) for p in (backup/'database.dump',backup/'state.tar.gz')})
        with patch.object(self.engine,'compose') as compose:
            with self.assertRaises(tarfile.FilterError):self.engine.restore(row,row['id'],{'api':'old','web':'old'},self.base_commit)
            compose.assert_not_called()

    def test_recovery_uses_persisted_candidate_flag_even_after_completion_phase(self):
        ready=self.ready();job=self.engine.submit('apply',commit=ready['commit'],release_id=ready['id']);row=self.engine.load(job['id'])
        row.update(candidate_may_have_started=True,phase='completed',backup_valid=True,previous_images={'api':'old','web':'old'},previous_commit=self.base_commit)
        with patch.object(self.engine,'restore') as restore:self.engine.recover(row)
        restore.assert_called_once_with(row,row['id'],row['previous_images'],self.base_commit)
        self.assertEqual(self.engine.load(ready['id'])['status'],'ready')

    def remote_fixture(self):
        remote=Path(self.temp.name)/'github.git'
        subprocess.run(['git','clone','-q','--bare',str(Path(self.temp.name)/'project'),str(remote)],check=True)
        branch=subprocess.check_output(['git','--git-dir='+str(remote),'symbolic-ref','--short','HEAD'],text=True).strip()
        self.engine.config.update(github_repository='owner/project',github_branch=branch)
        return remote,branch

    def test_publish_exact_verified_commit_and_refuse_remote_divergence(self):
        remote,branch=self.remote_fixture();ready=self.ready()
        with patch.object(self.engine,'remote',return_value=str(remote)):
            row=self.engine.submit('publish',commit=ready['commit'],release_id=ready['id'])
            self.engine.execute(self.engine.load(row['id']))
            result=self.engine.load(row['id'])
            self.assertEqual(result['status'],'completed')
            ref='refs/heads/cora/'+self.workspace['id']
            self.assertEqual(subprocess.check_output(['git','--git-dir='+str(remote),'rev-parse',ref],text=True).strip(),ready['commit'])
            self.assertIn('https://github.com/owner/project/compare/',result['compare_url'])
            # Advance the remote independently. Publishing the old commit must not rewind it.
            newer=self.change()
            (self.files/'app.py').write_text('value=99\n')
            newer=self.engine.commit_workspace(self.workspace['id'],'Remote advance')['commit']
            self.engine.git('push',str(remote),newer+':'+ref)
            row=self.engine.submit('publish',commit=ready['commit'],release_id=ready['id'])
            self.engine.execute(self.engine.load(row['id']))
            self.assertEqual(self.engine.load(row['id'])['status'],'failed')
            self.assertEqual(subprocess.check_output(['git','--git-dir='+str(remote),'rev-parse',ref],text=True).strip(),newer)
            self.assertEqual(self.engine.current()['commit'],self.base_commit)

    def test_new_workspace_fetches_github_without_changing_active_version(self):
        remote,branch=self.remote_fixture();newer=self.change()
        self.engine.git('push',str(remote),newer+':refs/heads/'+branch)
        with patch.object(self.engine,'remote',return_value=str(remote)):
            created=self.engine.create_workspace('From GitHub')
        self.assertEqual(created['source_commit'],newer)
        self.assertEqual(created['base_commit'],self.base_commit)
        self.assertEqual((self.engine.workspaces/created['id']/'files/app.py').read_text(),'value=2\n')
        self.assertEqual(self.engine.current()['commit'],self.base_commit)

    def test_unverified_commit_cannot_be_published(self):
        self.engine.config['github_repository']='owner/project'
        commit=self.change();row=self.engine.submit('prepare',self.workspace['id'],commit)
        full=self.engine.load(row['id']);full['status']='failed';self.engine.save(full)
        with self.assertRaises(ValueError):self.engine.submit('publish',commit=commit,release_id=row['id'])
