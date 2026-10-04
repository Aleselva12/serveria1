"""Host operations protect existing credentials and reject incomplete backups."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('deploy_manage',Path(__file__).resolve().parents[1]/'deploy/manage.py')
manage=importlib.util.module_from_spec(spec);spec.loader.exec_module(manage)


class HostDeploymentTests(unittest.TestCase):
    def test_init_creates_private_unique_credentials_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'deploy').mkdir()
            (root/'deploy/deploy.env.example').write_text((manage.ROOT/'deploy/deploy.env.example').read_text())
            with patch.object(manage,'ROOT',root),patch.object(manage,'ENV',root/'deploy.env'),patch.object(manage.os,'getuid',return_value=1000),patch.object(manage.os,'getgid',return_value=1000):
                manage.init();content=(root/'deploy.env').read_text()
                self.assertNotIn('GENERATED_BY_INIT',content)
                self.assertEqual(os.stat(root/'deploy.env').st_mode & 0o777,0o600)
                self.assertTrue((root/'state/audio/_transcripts').is_dir())
                with self.assertRaises(ValueError):manage.init()
                self.assertEqual((root/'deploy.env').read_text(),content)

    def test_corrupt_or_incomplete_backup_is_rejected_before_restore_stops_services(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)
            for name in ('database.dump','state.tar.gz','deploy.env'):(path/name).write_bytes(b'original')
            manifest={'version':1,'sha256':{name:manage.digest(path/name) for name in ('database.dump','state.tar.gz','deploy.env')}}
            (path/'manifest.json').write_text(json.dumps(manifest));manage.check_backup(path)
            (path/'database.dump').write_bytes(b'corrupt')
            with patch.object(manage,'compose') as compose:
                with self.assertRaises(ValueError):manage.restore(path)
                compose.assert_not_called()

    def test_backup_failure_keeps_application_stopped_and_has_no_valid_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'snapshot'
            with patch.object(manage,'compose',side_effect=[None,OSError('dump failure')]) as compose:
                with self.assertRaises(OSError):manage.backup(path)
                self.assertEqual(compose.call_count,2)
                self.assertEqual(compose.call_args_list[0].args,('stop','web','api'))
            self.assertFalse((path/'manifest.json').exists())
