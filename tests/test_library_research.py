import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from search_agent import search_tools as st
from core.governance import executables


def native(name, **kwargs):
    return next(e['fn'] for e in executables.values() if e['tool'].name == name)(**kwargs)


class LibraryResearchTests(unittest.TestCase):
    def make_symlink(self, link, target, **kwargs):
        try:
            link.symlink_to(target, **kwargs)
        except OSError as error:
            if os.name == "nt" and (getattr(error, "winerror", None) == 1314 or error.errno in {1, 13}):
                self.skipTest("Windows requires Developer Mode or symlink privileges for this test")
            raise

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'library'; self.root.mkdir()
        for target, value in [('library_workspace_root', lambda **kwargs: self.root), ('_require_permission', lambda action: None), ('ensure_runtime_active', lambda: None)]:
            p = patch.object(st, target, value); p.start(); self.addCleanup(p.stop)

    def test_names_and_contents_and_source_paths(self):
        (self.root/'preventivo Rossi.txt').write_text('totale 120 euro')
        (self.root/'nota.txt').write_text('Rossi vuole due ombrelloni')
        result = json.loads(native('search_local_documents', query='Rossi'))
        self.assertEqual({r['path'] for r in result['results']}, {'preventivo Rossi.txt', 'nota.txt'})
        self.assertIn('SOURCE_PATH: nota.txt', native('read_local_document', relative_path='nota.txt'))

    def test_missing_directory_is_not_reported_as_no_matches(self):
        result = json.loads(native('search_local_documents', query='Rossi', directory='missing'))
        self.assertEqual(result['status'], 'error')

    def test_corrupt_document_does_not_hide_other_results(self):
        (self.root/'bad.pdf').write_bytes(b'not a PDF')
        (self.root/'nota.txt').write_text('Rossi')
        result = json.loads(native('search_local_documents', query='Rossi'))
        self.assertEqual(result['skipped_contents'], 1)
        self.assertEqual(result['results'][0]['path'], 'nota.txt')

    def test_cancellation_and_timeout_are_not_swallowed(self):
        (self.root/'nota.txt').write_text('Rossi')
        for exception in (st.RunCancelled, st.RunTimedOut):
            with self.subTest(exception=exception), patch.object(st, 'ensure_runtime_active', side_effect=exception('stop')):
                with self.assertRaises(exception):
                    native('search_local_documents', query='Rossi')

    def test_public_supervisor_tools_are_read_only_and_permissions_apply(self):
        import tools
        from core.governance import tool_contract
        for name in ('library_list', 'library_search', 'library_read'):
            self.assertEqual(tool_contract(getattr(tools, name)).effect, 'read')
        with patch('core.permissions.require_permission', side_effect=PermissionError('denied')):
            with self.assertRaises(Exception):
                tools.library_search.invoke({'query':'Rossi'})

    def test_escape_symlink_and_protected_files_are_rejected(self):
        (self.root.parent/'outside.txt').write_text('secret')
        self.make_symlink(self.root / 'link.txt', self.root.parent / 'outside.txt')
        (self.root/'inside.txt').write_text('content')
        self.make_symlink(self.root / 'alias.txt', self.root / 'inside.txt')
        for path in ('../outside.txt', str(self.root.parent/'outside.txt'), 'link.txt', 'alias.txt', '.env'):
            with self.subTest(path=path):
                self.assertEqual(json.loads(native('read_local_document', relative_path=path))['status'], 'error')
        result = json.loads(native('list_local_documents'))
        self.assertEqual([r['path'] for r in result['documents']], ['inside.txt'])

    def test_runtime_activity_does_not_enter_diagnostics(self):
        from types import SimpleNamespace
        from core.runtime import current_run
        from core.observability import metadata_event
        token = current_run.set(SimpleNamespace(id='run', thread_id='thread'))
        try:
            with patch('core.event_bus.bus.publish') as publish:
                st._activity('search', query='Rossi', path='clienti')
                self.assertEqual(publish.call_args.kwargs['payload'], {'action':'search','query':'Rossi','path':'clienti'})
        finally: current_run.reset(token)
        self.assertIsNone(metadata_event({'type':'library.activity','payload':{'query':'private'}}))

    def test_automatic_tools_available_and_manual_selection_wins(self):
        from graph import _runtime_system_prompt
        names = _runtime_system_prompt([], request_text='ciao')[3]
        self.assertFalse({'library_list','library_search','library_read'} & set(names))
        requested = _runtime_system_prompt([], request_text='Elenca la Libreria IA')[3]
        self.assertTrue({'library_list','library_search','library_read'} <= set(requested))
        self.assertEqual(_runtime_system_prompt([], request_text='Cerca Rossi', manual_tools=[])[3], [])
