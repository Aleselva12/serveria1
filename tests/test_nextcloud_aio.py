import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from updater.nextcloud_aio import BACKUP, MASTER, NextcloudAIO


class NextcloudTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.aio=NextcloudAIO(self.tmp.name,sleep=lambda _:None)
        self.aio.preflight=Mock();self.aio.ready=Mock(return_value=True)
        self.aio.version=Mock(return_value={'versionstring':'33.0.7'})
        self.finished='old';self.scripts=[]
        def inspect(name):return {'id':'same','state':{'Running':False,'ExitCode':0,'FinishedAt':self.finished,'Health':{'Status':'healthy'}}}
        self.aio.inspect=Mock(side_effect=inspect)
        def script(update):
            self.scripts.append(update)
            if not update:self.finished='new'
        self.aio.script=Mock(side_effect=script)
    def test_backup_then_update_then_persisted_success(self):
        self.aio.execute()
        self.assertEqual(self.scripts,[False,True])
        self.assertEqual(NextcloudAIO(self.tmp.name).job['status'],'completed')
        self.assertEqual(self.aio.job['backupFinishedAt'],'new')
    def test_zero_exit_without_new_backup_never_updates(self):
        self.aio.script.side_effect=lambda update:self.scripts.append(update)
        self.aio.execute()
        self.assertEqual(self.scripts,[False]);self.assertEqual(self.aio.job['status'],'recovery_required')
    def test_restart_blocks_replay(self):
        self.aio.save(status='running',phase='update')
        self.assertEqual(NextcloudAIO(self.tmp.name).job['status'],'recovery_required')
    def test_failed_update_same_master_not_retried(self):
        def script(update):
            self.scripts.append(update)
            if update:raise RuntimeError('private detail')
            self.finished='new'
        self.aio.script.side_effect=script;self.aio.execute()
        self.assertEqual(self.scripts,[False,True])
        self.assertEqual(self.aio.job['status'],'recovery_required')
        self.assertNotIn('private detail',str(self.aio.job))
    def test_missing_health_never_completes(self):
        self.aio.ready.return_value=False;self.aio.execute()
        self.assertEqual(self.scripts,[False])
        self.assertEqual(self.aio.job['status'],'recovery_required')
    def test_modes_are_explicit_and_command_fixed(self):
        run=Mock(return_value='');aio=NextcloudAIO(self.tmp.name,run=run)
        aio.script(False)
        args=run.call_args.args[0]
        self.assertIn('DAILY_BACKUP=1',args);self.assertIn('AUTOMATIC_UPDATES=0',args)
        self.assertEqual(args[-2:],[MASTER,'/daily-backup.sh'])
    def test_master_replacement_gets_only_one_continuation(self):
        master=['old'];updates=[]
        previous=self.aio.inspect.side_effect
        def inspect(name):
            value=previous(name)
            if name==MASTER:value['id']=master[0]
            return value
        self.aio.inspect.side_effect=inspect
        def script(update):
            if not update:self.finished='new';return
            updates.append(True)
            if len(updates)==1:
                master[0]='new';raise RuntimeError('exec interrupted')
        self.aio.script.side_effect=script;self.aio.execute()
        self.assertEqual(len(updates),2);self.assertEqual(self.aio.job['status'],'completed')
    def test_recovery_confirmation_checks_aio_and_does_not_update(self):
        from updater.managed_apps import AppManager
        self.aio.save(status='recovery_required')
        manager=AppManager({'managed_apps_enabled':True,'nextcloud_aio_enabled':True},self.tmp.name)
        manager.nextcloud=self.aio
        with self.assertRaises(ValueError):manager.submit('nextcloud-aio','update')
        self.assertEqual(manager.submit('nextcloud-aio','acknowledge')['status'],'acknowledged')
        self.aio.preflight.assert_called_once();self.aio.script.assert_not_called()
