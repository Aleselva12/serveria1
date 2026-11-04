import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from programmer_agent import workspace as ws


class WorkspaceOrganizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, CORA_PROGRAMMER_WORKSPACE_ROOT=str(Path(self.temp.name) / 'work'))
        self.env.start(); self.addCleanup(self.env.stop)
        self.source = Path(self.temp.name) / 'source'
        self.source.mkdir()
        (self.source / 'sample.py').write_text('value = 1\n')

    def test_archive_and_rename_preserve_code_manifest_and_conversation_id(self):
        row = ws.create('My work', self.source)
        identifier = row['id']
        before = (ws.directory(identifier) / 'manifest.json').read_bytes()
        original = ws.read(identifier, 'sample.py')
        ws.write(identifier, 'sample.py', 'value = 2\n', original['sha256'])
        diff = ws.diff(identifier)
        result = ws.organize(identifier, title='Renamed work', archived=True)
        self.assertEqual(result['id'], identifier)
        self.assertTrue(result['archived'])
        self.assertEqual(result['title'], 'Renamed work')
        self.assertEqual(ws.diff(identifier), diff)
        self.assertEqual((ws.directory(identifier) / 'manifest.json').read_bytes(), before)
        self.assertEqual(ws.list_workspaces()[0]['title'], 'Renamed work')
        self.assertFalse(ws.organize(identifier, archived=False)['archived'])
        self.assertEqual(ws.read(identifier, 'sample.py')['content'], 'value = 2\n')

    def test_legacy_update_classification_survives_rename_and_new_updates_have_explicit_purpose(self):
        row = ws.create('Aggiornamento Cora dal branch main', self.source)
        self.assertEqual(ws.organize(row['id'], title='Old release')['purpose'], 'update')
        other = ws.create('Custom name', self.source)
        self.assertEqual(ws.organize(other['id'], purpose='update')['purpose'], 'update')
        with self.assertRaises(ValueError): ws.organize(other['id'], title='   ')
        with self.assertRaises(ValueError): ws.organize(other['id'], purpose='delete')

    def test_archived_rows_do_not_hide_older_work_after_previous_100_row_limit(self):
        for index in range(102):
            row = ws.create(f'Work {index}', self.source)
            if index: ws.organize(row['id'], archived=True)
        rows = ws.list_workspaces()
        self.assertEqual(len(rows), 102)
        self.assertEqual([r['title'] for r in rows if not r['archived']], ['Work 0'])
