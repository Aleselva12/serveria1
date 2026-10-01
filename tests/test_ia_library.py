import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.ia_library import router as library_router
from core.server_files import router as server_router


class LibraryCopiesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.server = self.base / 'server'
        self.library = self.base / 'knowledge'
        self.originals = self.base / 'originals'
        for path in [self.server, self.library, self.originals]:
            path.mkdir()
        self.env = patch.dict(os.environ, {
            'CORA_FILES_TOKEN': 'owner',
            'CORA_FILE_ROOTS': json.dumps([{'id': 'server', 'path': str(self.server), 'writable': True}]),
            'CORA_KNOWLEDGE_ROOT': str(self.library),
            'CORA_LIBRARY_ORIGINALS_ROOT': str(self.originals),
            'CORA_FILES_MAX_UPLOAD_BYTES': '10',
        })
        self.env.start()
        app = FastAPI()
        app.include_router(server_router)
        app.include_router(library_router)
        self.client = TestClient(app, headers={'Authorization': 'Bearer owner'})
        self.prefix = '/api/v1/library/files'

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.temp.cleanup()

    def import_file(self, source='report.txt', destination='report.txt'):
        return self.client.post(self.prefix + '/import', json={'source_root_id': 'server', 'source_path': source, 'destination': destination})

    def post(self, endpoint, **body):
        return self.client.post(self.prefix + endpoint, json={'root_id': 'library', **body})

    def test_import_is_independent_and_never_moves_original(self):
        source = self.server / 'report.txt'
        source.write_text('original')
        response = self.import_file()
        self.assertEqual(response.status_code, 201)
        copy = self.library / 'report.txt'
        self.assertEqual(source.read_text(), copy.read_text())
        self.assertNotEqual(source.stat().st_ino, copy.stat().st_ino)
        copy.write_text('IA work')
        self.assertEqual(source.read_text(), 'original')
        self.assertEqual(self.import_file().status_code, 409)
        self.assertEqual(copy.read_text(), 'IA work')

    def test_library_upload_preserves_original_visible_in_server(self):
        response = self.client.post(self.prefix + '/upload', data={'path': ''}, files={'file': ('report.txt', b'hello')})
        self.assertEqual(response.status_code, 201)
        data = response.json()
        saved = self.originals / data['original']['path']
        self.assertEqual(saved.read_bytes(), b'hello')
        self.assertEqual((self.library / 'report.txt').read_bytes(), b'hello')
        roots = self.client.get('/api/v1/server/files/roots').json()['roots']
        self.assertIn('ia-originals', [r['id'] for r in roots])
        download = self.client.get('/api/v1/server/files/download', params={'root_id': 'ia-originals', 'path': data['original']['path']})
        self.assertEqual(download.content, b'hello')
        self.assertNotEqual(saved.stat().st_ino, (self.library / 'report.txt').stat().st_ino)

    def test_trash_rename_restore_only_touch_ia_copy(self):
        source = self.server / 'report.txt'
        source.write_text('original')
        self.import_file()
        self.assertEqual(self.post('/transfer', path='report.txt', destination='renamed.txt').status_code, 200)
        ident = self.post('/trash', path='renamed.txt').json()['id']
        self.assertEqual(source.read_text(), 'original')
        self.assertFalse((self.library / 'renamed.txt').exists())
        self.assertEqual(self.post('/restore', id=ident).status_code, 200)
        self.assertEqual(source.read_text(), 'original')

    def test_failed_copy_keeps_completed_upload_original(self):
        with patch('core.ia_library.copy_document', side_effect=OSError('disk full')):
            response = self.client.post(self.prefix + '/upload', files={'file': ('report.txt', b'hello')})
        self.assertEqual(response.status_code, 503)
        self.assertIn('originale conservato', response.json()['detail'])
        self.assertEqual(len(list(self.originals.glob('*/report.txt'))), 1)
        self.assertFalse((self.library / 'report.txt').exists())

    def test_large_upload_and_conflict_do_not_create_or_replace_copies(self):
        response = self.client.post(self.prefix + '/upload', files={'file': ('large.txt', b'x' * 11)})
        self.assertEqual(response.status_code, 413)
        self.assertFalse((self.library / 'large.txt').exists())
        self.assertEqual(list(self.originals.glob('*/large.txt')), [])
        (self.library / 'existing').write_text('keep')
        response = self.client.post(self.prefix + '/upload', files={'file': ('existing', b'new')})
        self.assertEqual(response.status_code, 409)
        self.assertEqual((self.library / 'existing').read_text(), 'keep')

    def test_library_browsing_and_permissions(self):
        (self.library / 'a.txt').write_text('hello')
        result = self.client.get(self.prefix + '/children', params={'root_id': 'library', 'path': ''})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['items'][0]['name'], 'a.txt')
        self.assertEqual(self.client.get(self.prefix + '/roots', headers={'Authorization': ''}).status_code, 401)
        self.assertEqual(self.client.get('/api/v1/server/files/children', params={'root_id': 'library'}).status_code, 404)
        self.assertEqual(self.import_file(source='../outside').status_code, 400)
        self.assertEqual(self.import_file(destination='../outside').status_code, 400)
        (self.server / 'link').symlink_to(self.base)
        self.assertEqual(self.import_file(source='link').status_code, 403)

    def test_same_or_nested_originals_and_library_are_refused(self):
        for path in [str(self.originals), str(self.originals / 'nested'), str(self.base)]:
            with patch.dict(os.environ, {'CORA_KNOWLEDGE_ROOT': path}):
                self.assertEqual(self.client.get(self.prefix + '/roots').status_code, 503)

    def test_missing_explicit_library_is_not_created(self):
        path = self.base / 'not-mounted'
        with patch.dict(os.environ, {'CORA_KNOWLEDGE_ROOT': str(path)}):
            self.assertFalse(self.client.get(self.prefix + '/roots').json()['roots'][0]['available'])
            self.assertEqual(self.import_file().status_code, 503)
        self.assertFalse(path.exists())

    def test_import_from_readonly_server_root_is_allowed(self):
        (self.server / 'report.txt').write_text('read only')
        with patch.dict(os.environ, {'CORA_FILE_ROOTS': json.dumps([{'id': 'server', 'path': str(self.server), 'writable': False}])}):
            self.assertEqual(self.import_file().status_code, 201)
        self.assertEqual((self.server / 'report.txt').read_text(), 'read only')


if __name__ == '__main__':
    unittest.main()
