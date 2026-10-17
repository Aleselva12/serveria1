import io
import unittest
from docx import Document
from core.library_tools import _document_bytes, digest


class DocumentEditingUnitTests(unittest.TestCase):
    def test_text_append_keeps_original(self):
        self.assertEqual(_document_bytes('.md', 'secondo', original=b'primo').decode(),
                         'primo\nsecondo')
        self.assertEqual(_document_bytes('.txt', 'secondo', original=b'primo\n').decode(),
                         'primo\nsecondo')

    def test_word_append_preserves_paragraphs_and_tables(self):
        doc = Document()
        doc.add_heading('Cliente Rossi', level=1)
        table = doc.add_table(rows=1, cols=1)
        table.cell(0, 0).text = 'Ordine 123'
        stream = io.BytesIO()
        doc.save(stream)
        updated = Document(io.BytesIO(_document_bytes('.docx', 'Nuovo appunto', original=stream.getvalue())))
        self.assertEqual(updated.paragraphs[0].text, 'Cliente Rossi')
        self.assertEqual(updated.paragraphs[-1].text, 'Nuovo appunto')
        self.assertEqual(updated.tables[0].cell(0, 0).text, 'Ordine 123')

    def test_only_editable_extensions(self):
        for suffix in ('.pdf', '.xlsx', '.py'):
            with self.assertRaises(ValueError):
                _document_bytes(suffix, 'data')

    def test_checksum_changes_with_content(self):
        self.assertNotEqual(digest(b'old'), digest(b'new'))


if __name__ == '__main__':
    unittest.main()
