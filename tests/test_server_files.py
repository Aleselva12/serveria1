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
        self.originals = self.base / 'originals'
        self.originals.mkdir()
        self.env = patch.dict(os.environ, {
            'CORA_FILES_TOKEN': 'test-owner-token',
            'CORA_LIBRARY_ORIGINALS_ROOT': str(self.originals),
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

    def test_roots_do_not_expose_absolute_paths(self):
        self.assertTrue(all('path' not in root for root in self.get('/roots').json()['roots']))

    def test_reserved_names_are_case_insensitive(self):
        self.assertEqual(self.get('/children', path='.CORA-Trash').status_code, 400)
        self.assertEqual(self.post('/folders', path='.Cora-Staging').status_code, 400)

    def test_invalid_transfer_mode_is_validation_error(self):
        self.upload()
        self.assertEqual(self.post('/transfer', path='hello.txt', destination='b.txt', mode='x').status_code, 422)

    def test_long_name_is_bad_request(self):
        self.assertEqual(self.post('/folders', path='a' * 300).status_code, 400)

    def test_loopback_accepts_ipv4_mapped_address(self):
        from core.server_files import is_loopback
        self.assertTrue(is_loopback('::ffff:127.0.0.1'))
        self.assertTrue(is_loopback('::1'))
        self.assertFalse(is_loopback('192.168.1.5'))
        self.assertFalse(is_loopback(''))

    def test_same_prefix_sibling_and_all_public_path_inputs_are_confined(self):
        sibling=self.base/'files-private';sibling.mkdir();secret=sibling/'secret.txt';secret.write_text('private')
        (self.data/'source.txt').write_text('source')
        for unsafe in ('../files-private/secret.txt', str(secret), 'nested/../../files-private/secret.txt'):
            for route in ('/children','/download','/preview','/search'):
                response=self.get(route,path=unsafe,query='secret')
                self.assertEqual(response.status_code,400,(route,unsafe))
            for route in ('/folders','/trash'):
                self.assertEqual(self.post(route,path=unsafe).status_code,400)
            for mode in ('copy','move'):
                self.assertEqual(self.post('/transfer',path=unsafe,destination='copy',mode=mode).status_code,400)
                self.assertEqual(self.post('/transfer',path='source.txt',destination=unsafe,mode=mode).status_code,400)
            self.assertEqual(self.upload(path=unsafe).status_code,400)
        self.assertEqual(secret.read_text(),'private');self.assertEqual((self.data/'source.txt').read_text(),'source')

    def test_tampered_trash_destination_and_metadata_links_are_rejected(self):
        self.upload();ident=self.post('/trash',path='hello.txt').json()['id']
        slot=self.data/'.cora-trash'/ident;metadata=slot/'metadata.json'
        data=json.loads(metadata.read_text());data['path']='../escape.txt';metadata.write_text(json.dumps(data))
        self.assertEqual(self.post('/restore',id=ident).status_code,400)
        self.assertFalse((self.base/'escape.txt').exists());self.assertTrue((slot/'content').exists())
        metadata.unlink();outside=self.base/'metadata.json';outside.write_text(json.dumps({'path':'safe.txt'}));metadata.symlink_to(outside)
        self.assertEqual(self.post('/restore',id=ident).status_code,403)
        self.assertEqual(self.get('/trash').json()['items'],[])

    def test_confined_path_rejects_sibling_prefix_and_internal_links(self):
        from core.confined_paths import confined_path
        from fastapi import HTTPException
        sibling=self.base/'files-private';sibling.mkdir()
        with self.assertRaises(HTTPException):confined_path(self.data,sibling/'secret')
        (self.data/'folder').mkdir();(self.data/'alias').symlink_to(self.data/'folder',target_is_directory=True)
        with self.assertRaises(HTTPException):confined_path(self.data,self.data/'alias/file')
        self.assertEqual(confined_path(self.data,self.data),self.data)


if __name__ == '__main__':
    unittest.main()
