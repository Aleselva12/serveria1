import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

from updater import data_backups as backup
from updater.engine import atomic, file_digest


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        control=self.root/'control';control.mkdir()
        state=self.root/'state';state.mkdir()
        self.engine=Mock(root=control,state=state)
        self.engine.config={}
        self.settings={'destination':str(self.root/'backups'),'audit_sha256':'approved',
                       'age_recipient':'age1example','keep':2}

    def test_changed_mounts_fail_before_stopping_any_service(self):
        with patch.object(backup,'audit',return_value={'audit_sha256':'changed'}):
            with self.assertRaises(ValueError):backup.create(self.engine,self.settings)
        self.engine.compose.assert_not_called()

    def test_retention_does_not_count_or_remove_incomplete_corrupt_or_unrelated(self):
        root=self.root/'backups';root.mkdir()
        for index in range(5):
            folder=root/f'cora-000{index}';folder.mkdir()
            (folder/'data.tar.age').write_bytes(b'encrypted')
            atomic(folder/'complete.json',{'sha256':file_digest(folder/'data.tar.age')})
        (root/'cora-0004/data.tar.age').write_bytes(b'corrupted')
        (root/'cora-incomplete').mkdir();(root/'release-backup').mkdir()
        backup.prune(root,2)
        self.assertFalse((root/'cora-0000').exists())
        self.assertFalse((root/'cora-0001').exists())
        for name in ('cora-0002','cora-0003','cora-0004','cora-incomplete','release-backup'):
            self.assertTrue((root/name).exists())

    def test_dump_failure_restarts_pinned_images_and_never_prunes(self):
        self.engine.images.return_value={'api':'sha256:old-api','web':'sha256:old-web'}
        self.engine.compose.side_effect=[None,RuntimeError('dump failed'),None]
        with patch.object(backup,'audit',return_value={'audit_sha256':'approved'}),patch.object(backup.shutil,'which',return_value='/usr/bin/age'),patch.object(backup,'prune') as prune:
            with self.assertRaises(RuntimeError):backup.create(self.engine,self.settings)
        prune.assert_not_called()
        self.assertEqual(self.engine.compose.call_args.kwargs['images'],self.engine.images.return_value)
        self.assertFalse((self.engine.root/'data-backup-pending.json').exists())
        self.assertEqual(list((self.root/'backups').glob('*/complete.json')),[])

    def test_failed_restart_keeps_recovery_marker_and_boot_recovers_exact_images(self):
        images={'api':'sha256:old','web':'sha256:old-web'}
        atomic(self.engine.root/'data-backup-pending.json',{'images':images})
        self.engine.compose.side_effect=RuntimeError('unhealthy')
        with self.assertRaises(RuntimeError):backup.recover_pending(self.engine)
        self.assertTrue((self.engine.root/'data-backup-pending.json').exists())
        self.engine.compose.side_effect=None
        backup.recover_pending(self.engine)
        self.assertEqual(self.engine.compose.call_args.kwargs['images'],images)
        self.assertFalse((self.engine.root/'data-backup-pending.json').exists())

    def test_unapproved_or_wrong_state_mount_audit_is_rejected(self):
        self.engine.compose.return_value='container'
        self.engine.cmd.return_value=json.dumps([{'Destination':'/state','Type':'bind','Source':str(self.root/'other')}])
        with self.assertRaises(ValueError):backup.audit(self.engine)

    def test_restore_checks_archive_traversal_before_stopping_services(self):
        from deploy import manage
        folder=self.root/'plain';folder.mkdir()
        with tarfile.open(folder/'state.tar.gz','w:gz') as archive:
            entry=tarfile.TarInfo('../escape');entry.size=1
            archive.addfile(entry,io.BytesIO(b'x'))
        for name in ('database.dump','deploy.env'):(folder/name).write_bytes(b'x')
        atomic(folder/'manifest.json',{'version':1,'sha256':{p.name:file_digest(p) for p in folder.iterdir()}})
        with patch.object(manage,'compose') as compose:
            with self.assertRaises(ValueError):manage.restore(folder)
        compose.assert_not_called()

    @unittest.skipUnless(shutil.which('age') and shutil.which('age-keygen'),'Requires real age binaries (Linux CI)')
    def test_encrypted_roundtrip_and_wrong_key_rejected(self):
        identity=self.root/'identity.txt'
        subprocess.run(['age-keygen','-o',str(identity)],check=True,capture_output=True)
        recipient=subprocess.check_output(['age-keygen','-y',str(identity)],text=True).strip()
        settings={**self.settings,'age_recipient':recipient}
        for name in ('compose.json','config.json','current.json','bridge.token'):
            (self.engine.root/name).write_text('private fixture')
        self.engine.images.return_value={'api':'sha256:api','web':'sha256:web'}
        def compose(*args,**kwargs):
            output=kwargs.get('stdout')
            if output:
                if 'pg_dump' in ' '.join(args):output.write(b'fixture dump')
                else:
                    with tarfile.open(fileobj=output,mode='w:gz') as archive:
                        item=tarfile.TarInfo('./proof.txt');item.size=5;archive.addfile(item,io.BytesIO(b'proof'))
            return ''
        self.engine.compose.side_effect=compose
        with patch.object(backup,'audit',return_value={'audit_sha256':'approved'}):
            folder=backup.create(self.engine,settings)
        target=self.root/'unpacked'
        backup.unpack(folder,target,identity)
        self.assertEqual((target/'bridge.token').read_text(),'private fixture')
        self.assertNotIn(b'private fixture',(folder/'data.tar.age').read_bytes())
        wrong=self.root/'wrong.txt'
        subprocess.run(['age-keygen','-o',str(wrong)],check=True,capture_output=True)
        with self.assertRaises(subprocess.CalledProcessError):backup.unpack(folder,self.root/'wrong-target',wrong)


if __name__=='__main__':unittest.main()
