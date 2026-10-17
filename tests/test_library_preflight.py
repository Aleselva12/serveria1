import json
import unittest
from unittest.mock import patch
from core import library_preflight as preflight


class LibraryPreflightTests(unittest.TestCase):
    def test_explicit_library_path_is_discovered(self):
        self.assertEqual(preflight.document_query('/Libreria Ia/collaudo'), 'collaudo')
        self.assertEqual(preflight.document_query('Il file "collaudo" è nella Libreria IA'), 'collaudo')

    def test_unrelated_query_does_not_trigger_lookup(self):
        self.assertIsNone(preflight.document_query('Ciao, come stai?'))
        self.assertIsNone(preflight.document_query('Programma chiamato "collaudo"'))

    @patch('core.runtime_context.ensure_runtime_active', return_value=None)
    @patch('tools.library_read')
    @patch('tools.library_search')
    def test_single_match_is_read_with_tools(self, search, read, _runtime):
        search.invoke.return_value = json.dumps({'results': [{'path': 'test/collaudo.txt'}]})
        read.invoke.return_value = 'SOURCE_PATH: test/collaudo.txt\ncontenuto'
        result = preflight.preload('/Libreria Ia/collaudo', ['library_search', 'library_read'])
        self.assertIn('SOURCE_PATH: test/collaudo.txt', result)
        search.invoke.assert_called_once()
        read.invoke.assert_called_once_with({'relative_path': 'test/collaudo.txt'})

    @patch('tools.library_search')
    def test_manual_selection_disables_preflight(self, search):
        self.assertEqual(preflight.preload('/Libreria Ia/collaudo', []), '')
        search.invoke.assert_not_called()

    @patch('core.runtime_context.ensure_runtime_active', return_value=None)
    @patch('tools.library_read')
    @patch('tools.library_search')
    def test_ambiguous_names_are_not_read(self, search, read, _runtime):
        search.invoke.return_value = json.dumps({'results': [{'path': 'a/collaudo.txt'}, {'path': 'b/collaudo.txt'}]})
        value = preflight.preload('/Libreria Ia/collaudo', ['library_search', 'library_read'])
        self.assertIn('a/collaudo.txt', value)
        read.invoke.assert_not_called()

if __name__ == '__main__':
    unittest.main()
