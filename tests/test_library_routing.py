import json
import unittest
from unittest.mock import patch
from core.library_routing import library_intent, list_requested, list_documents_direct


class LibraryRoutingTests(unittest.TestCase):
    def test_library_vs_repository(self):
        self.assertTrue(library_intent("utilizza library_list e mostra i file della libreria"))
        self.assertTrue(list_requested("mostra i file della libreria IA"))
        self.assertFalse(library_intent("elenca i file della repository"))
        self.assertFalse(library_intent("cerca nella libreria e nel codice sorgente"))
        self.assertFalse(list_requested("aggiungi un appunto nella libreria IA"))

    @patch('tools.library_list')
    def test_direct_listing_uses_real_tool_output(self, tool):
        tool.invoke.return_value = json.dumps({"documents": [
            {"path":"collaudo.docx","type":".docx","size_bytes":13493},
            {"path":"IA_perfect_spec.md","type":".md","size_bytes":7548}]})
        result = list_documents_direct()
        self.assertIn("collaudo.docx", result)
        self.assertIn("IA_perfect_spec.md", result)
        self.assertNotIn(".gitignore", result)
        tool.invoke.assert_called_once_with({"directory":".","recursive":True})

    @patch('tools.library_list')
    def test_error_is_not_reported_as_empty_library(self, tool):
        tool.invoke.return_value = json.dumps({"status":"error","error":"permission denied"})
        self.assertIn("permission denied", list_documents_direct())

    def test_supervisor_binding_does_not_expose_repository_for_library(self):
        from graph import _runtime_system_prompt
        tools = _runtime_system_prompt([], request_text='Elenca file nella Libreria IA')[3]
        self.assertIn('library_list', tools)
        self.assertNotIn('list_project_files', tools)
        self.assertNotIn('read_project_file', tools)
        other = _runtime_system_prompt([], request_text='elenca file della repository')[3]
        self.assertIn('list_project_files', other)

if __name__ == '__main__':
    unittest.main()
