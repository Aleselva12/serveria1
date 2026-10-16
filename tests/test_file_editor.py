import os
from unittest.mock import patch
import test_server_files as server_tests


class FileEditorTests(server_tests.ServerFilesTests):
    def test_edit_backup_conflict_and_mode(self):
        target = self.data / 'code.py'
        target.write_bytes(b'print("ciao")\r\n')
        target.chmod(0o640)
        opened = self.get('/text', path='code.py')
        self.assertIn('no-store', opened.headers['cache-control'])
        data = opened.json()
        self.assertEqual(data['text'], 'print("ciao")\r\n')
        result = self.post('/text', path='code.py', revision=data['revision'], text='print("nuovo")\r\n')
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual((self.data / result.json()['backupPath']).read_bytes(), b'print("ciao")\r\n')
        self.assertEqual(target.read_bytes(), b'print("nuovo")\r\n')
        if os.name == 'posix': self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.post('/text', path='code.py', revision=data['revision'], text='stale').status_code, 409)

    def test_readonly_binary_size_and_links(self):
        (self.readonly / 'x').write_text('old')
        rev = self.get('/text', root_id='ro', path='x').json()['revision']
        self.assertEqual(self.post('/text', root_id='ro', path='x', revision=rev, text='new').status_code, 403)
        (self.data / 'binary').write_bytes(b'a\x00b')
        self.assertEqual(self.get('/text', path='binary').status_code, 415)
        (self.data / 'big').write_bytes(b'a' * (1024*1024+1))
        self.assertEqual(self.get('/text', path='big').status_code, 413)
        (self.data / 'nonutf').write_bytes(b'\xff')
        self.assertEqual(self.get('/text', path='nonutf').status_code, 415)
        self.make_symlink(self.data / 'link', self.readonly / 'x')
        self.assertEqual(self.get('/text', path='link').status_code, 403)
        self.assertEqual(self.get('/text', path='../readonly/x').status_code, 400)
        self.assertEqual(self.client.post(self.prefix+'/text', headers={'Authorization': ''}, json={'root_id':'ro','path':'x','revision':rev,'text':'x'}).status_code, 401)

    def test_failed_publish_retains_original_and_backup(self):
        target = self.data / 'x'
        target.write_bytes(b'original')
        rev = self.get('/text', path='x').json()['revision']
        with patch('core.file_editor.os.replace', side_effect=PermissionError):
            self.assertEqual(self.post('/text', path='x', revision=rev, text='new').status_code, 403)
        self.assertEqual(target.read_bytes(), b'original')
        self.assertEqual(next(self.data.glob('cora-backup-*.bak')).read_bytes(), b'original')
        self.assertFalse(list(self.data.glob('.cora-edit-*')))

    def test_external_change_hardlink_and_byte_limit_leave_original_untouched(self):
        target = self.data / 'x'
        target.write_bytes(b'old')
        rev = self.get('/text', path='x').json()['revision']
        target.write_bytes(b'external')
        self.assertEqual(self.post('/text', path='x', revision=rev, text='draft').status_code,409)
        rev = self.get('/text', path='x').json()['revision']
        self.assertEqual(self.post('/text', path='x', revision=rev, text='è' * 600000).status_code,413)
        self.assertEqual(self.post('/text', path='x', revision=rev, text='a\x00b').status_code,415)
        os.link(target, self.data / 'other')
        self.assertEqual(self.post('/text', path='x', revision=rev, text='new').status_code,409)
        self.assertEqual(target.read_bytes(),b'external')
        self.assertFalse(list(self.data.glob('cora-backup-*.bak')))
