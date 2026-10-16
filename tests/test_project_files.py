import json
import tempfile
import unittest
from pathlib import Path
from deploy.project_files import configure


class ProjectFilesTests(unittest.TestCase):
    def test_updater_preserves_settings_and_backups_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project = base / 'project'; project.mkdir()
            (project / 'compose.yml').write_text('services: {}')
            root = base / 'updater'; root.mkdir()
            config = {'services': {'api': {'image':'old-api', 'environment': {'SECRET':'kept', 'CORA_FILE_ROOTS': json.dumps([{'id':'server','path':'/host','writable':False}])}, 'volumes':[{'target':'/host','read_only':True,'source':'/'}]}, 'web': {'image':'old-web'}}}
            path = root / 'compose.json'; path.write_text(json.dumps(config))
            backup = configure(root, project)
            self.assertEqual(json.loads(backup.read_text()), config)
            configure(root, project)
            changed = json.loads(path.read_text())
            api = changed['services']['api']
            self.assertEqual(api['environment']['SECRET'], 'kept')
            self.assertEqual(changed['services']['web'], config['services']['web'])
            roots = json.loads(api['environment']['CORA_FILE_ROOTS'])
            self.assertEqual(len([r for r in roots if r['id']=='project']),1)
            self.assertEqual(roots[0]['writable'],False)
            self.assertEqual(api['volumes'][0],config['services']['api']['volumes'][0])
            self.assertEqual(api['volumes'][1]['source'],str(project))
            self.assertEqual(len(api['volumes']),2)
