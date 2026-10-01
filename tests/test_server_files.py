import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.server_files import router


class ServerFilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.data = self.base / 'files'
        self.data.mkdir()
        self.readonly = self.base / 'readonly'
        self.readonly.mkdir()
        self.env = patch.dict(os.environ, {
            'CORA_FILES_TOKEN': 'test-owner-token',
            'CORA_FILE_ROOTS': json.dumps([
                {'id': 'files', 'path': str(self.data), 'writable': True},
                {'id': 'ro', 'path': str(self.readonly), 'writable': False},
                {'id': 'absent', 'path': str(self.base / 'not-mounted')},
            ]),
            'CORA_FILES_MAX_UPLOAD_BYTES': '10',
        })
        self.env.start()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app, headers={'Authorization': 'Bearer test-owner-token'})
        self.prefix = '/api/v1/server/files'

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.temp.cleanup()

    def get(self, route, **params):
        return self.client.get(self.prefix + route, params={'root_id': 'files', **params})

    def post(self, route, **data):
        return self.client.post(self.prefix + route, json={'root_id': 'files', **data})

    def upload(self, name='hello.txt', data=b'hello', root_id='files', path=''):
        return self.client.post(self.prefix + '/upload', data={'root_id': root_id, 'path': path}, files={'file': (name, data)})

    def test_access_requires_owner_token(self):
        response = self.client.get(self.prefix + '/roots', headers={'Authorization': ''})
        self.assertEqual(response.status_code, 401)
        with patch.dict(os.environ, {'CORA_FILES_TOKEN': ''}):
            self.assertEqual(self.get('/children').status_code, 403)

    def test_roots_report_missing_disk_without_creating_it(self):
        data = self.get('/roots').json()['roots']
        self.assertTrue(data[0]['available'])
        self.assertFalse(data[2]['available'])
        self.assertFalse((self.base / 'not-mounted').exists())
        self.assertEqual(self.get('/children', root_id='absent').status_code, 503)

    def test_listing_filter_pagination_and_directories(self):
        (self.data / 'folder').mkdir()
        (self.data / 'Alpha.txt').write_text('hello')
        (self.data / 'Beta.txt').write_text('world')
        data = self.get('/children', limit=1).json()
        self.assertEqual(data['total'], 3)
        self.assertEqual(data['items'][0]['kind'], 'folder')
        self.assertEqual(self.get('/children', query='ALPHA').json()['total'], 1)
        self.assertEqual(self.get('/children', path='Alpha.txt').status_code, 400)
        self.assertEqual(self.get('/children', path='missing').status_code, 404)

    def test_traversal_and_symbolic_links_are_blocked(self):
        for path in ['../', '/etc', 'folder/../x', 'C:/x', 'a\\b', '.cora-trash/x', '.cora-staging/x']:
            self.assertEqual(self.get('/children', path=path).status_code, 400, path)
        outside = self.base / 'secret'
        outside.write_text('secret')
        (self.data / 'link').symlink_to(outside)
        self.assertEqual(self.get('/download', path='link').status_code, 403)
        self.assertEqual(self.get('/children').json()['items'][0]['kind'], 'link')

    def test_upload_and_download_are_exact_and_no_overwrite(self):
        self.assertEqual(self.upload().status_code, 201)
        self.assertEqual(self.get('/download', path='hello.txt').content, b'hello')
        self.assertEqual(self.upload(data=b'other').status_code, 409)
        self.assertEqual((self.data / 'hello.txt').read_bytes(), b'hello')
        self.assertEqual(self.upload(name='../escape').status_code, 400)
        self.assertEqual(self.upload(name='large', data=b'x' * 11).status_code, 413)
        self.assertFalse((self.data / 'large').exists())
        self.assertEqual(list((self.data / '.cora-staging').iterdir()), [])
        self.assertNotIn('.cora-staging', [n['name'] for n in self.get('/children').json()['items']])

    def test_readonly_rejects_all_mutations(self):
        (self.readonly / 'document').write_text('hello')
        self.assertEqual(self.get('/download', root_id='ro', path='document').content, b'hello')
        self.assertEqual(self.upload(root_id='ro').status_code, 403)
        for route, data in [('/folders', {'path': 'new'}), ('/trash', {'path': 'document'}),
                            ('/transfer', {'path': 'document', 'destination': 'new'}),
                            ('/restore', {'id': 'a' * 32})]:
            self.assertEqual(self.post(route, root_id='ro', **data).status_code, 403)

    def test_create_move_copy_and_conflicts(self):
        self.assertEqual(self.post('/folders', path='folder').status_code, 201)
        self.upload()
        self.assertEqual(self.post('/transfer', path='hello.txt', destination='folder/renamed', mode='move').status_code, 200)
        self.assertFalse((self.data / 'hello.txt').exists())
        self.assertEqual(self.post('/transfer', path='folder', destination='copy', mode='copy').status_code, 200)
        self.assertEqual((self.data / 'copy' / 'renamed').read_bytes(), b'hello')
        self.assertEqual(self.post('/transfer', path='folder', destination='copy').status_code, 409)
        self.assertEqual(self.post('/transfer', path='folder', destination='folder/nested').status_code, 400)
        self.assertEqual(self.post('/transfer', path='folder', destination='unknown/nested').status_code, 404)

    def test_copy_tree_does_not_follow_embedded_links(self):
        folder = self.data / 'folder'
        folder.mkdir()
        (folder / 'escape').symlink_to(self.base)
        self.assertEqual(self.post('/transfer', path='folder', destination='copy', mode='copy').status_code, 403)
        self.assertFalse((self.data / 'copy').exists())

    def test_trash_restore_and_conflicting_original(self):
        self.upload()
        result = self.post('/trash', path='hello.txt')
        self.assertEqual(result.status_code, 201)
        ident = result.json()['id']
        self.assertEqual(self.get('/trash').json()['items'][0]['path'], 'hello.txt')
        self.assertEqual(self.get('/children').json()['total'], 0)
        self.upload(data=b'new')
        self.assertEqual(self.post('/restore', id=ident).status_code, 409)
        self.assertEqual((self.data / 'hello.txt').read_bytes(), b'new')
        (self.data / 'hello.txt').unlink()
        self.assertEqual(self.post('/restore', id=ident).status_code, 200)
        self.assertEqual((self.data / 'hello.txt').read_bytes(), b'hello')
        self.assertEqual(self.get('/trash').json()['items'], [])
        self.assertEqual(self.post('/restore', id='../bad').status_code, 400)

    def test_folder_trash_persists_and_requires_existing_parent_to_restore(self):
        self.post('/folders', path='parent')
        self.upload(path='parent')
        ident = self.post('/trash', path='parent/hello.txt').json()['id']
        (self.data / 'parent').rmdir()
        self.assertEqual(self.post('/restore', id=ident).status_code, 404)
        self.post('/folders', path='parent')
        self.assertEqual(self.post('/restore', id=ident).status_code, 200)
        ident = self.post('/trash', path='parent').json()['id']
        self.assertEqual(self.post('/restore', id=ident).status_code, 200)
        self.assertEqual((self.data / 'parent/hello.txt').read_bytes(), b'hello')

    def test_invalid_root_configuration_fails_explicitly(self):
        with patch.dict(os.environ, {'CORA_FILE_ROOTS': 'not-json'}):
            self.assertEqual(self.get('/roots').status_code, 503)


if __name__ == '__main__':
    unittest.main()
