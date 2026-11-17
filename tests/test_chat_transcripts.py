"""Markdown transcripts of chat conversations."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from core.domain import transcripts

CONVERSATION = {"id": "c1", "title": "Preventivo: Rossi / ombrelloni", "created_at": "2026-11-17T09:30:00",
                "updated_at": "2026-11-17T10:00:00"}


class TranscriptTests(unittest.TestCase):
    def test_path_is_grouped_by_month_with_a_safe_slug(self):
        with patch.object(transcripts, "TRANSCRIPT_ROOT", Path("/root-x")):
            path = transcripts.transcript_path(CONVERSATION)
            same = transcripts.transcript_path({**CONVERSATION, "created_at": datetime(2026, 11, 17, 9, 30)})
        self.assertEqual(path, same)
        self.assertEqual(path, Path("/root-x/2026/11/2026-11-17_Preventivo-Rossi-ombrelloni_c1.md"))

    def test_slug_keeps_italian_letters_and_falls_back(self):
        self.assertEqual(transcripts._slug("  Città è più  "), "Città-è-più")
        self.assertEqual(transcripts._slug("///"), "chat")
        self.assertEqual(len(transcripts._slug("a" * 200)), 80)

    def test_render_labels_roles_and_adds_agent_and_model(self):
        text = transcripts.render_transcript(CONVERSATION, [
            {"role": "user", "content": "Ciao", "created_at": "t1"},
            {"role": "assistant", "content": "Eccomi", "created_at": "t2", "agent_id": "supervisor", "model_id": "qwen3:8b"},
            {"role": "tool", "content": "dati", "created_at": "t3", "model_id": "m"},
        ])
        self.assertTrue(text.startswith("# Preventivo: Rossi / ombrelloni\n"))
        self.assertIn("## Utente — t1\n", text)
        self.assertIn("## Cora — t2 · supervisor / qwen3:8b\n", text)
        self.assertIn("## tool — t3 · m\n", text)
        self.assertTrue(text.endswith("---\n"))
        self.assertFalse(text.endswith("\n\n"))

    def test_write_replaces_the_file_without_leaving_temporary_files(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(transcripts, "TRANSCRIPT_ROOT", Path(folder)):
            first = transcripts.write_transcript(CONVERSATION, [{"role": "user", "content": "uno", "created_at": "t"}])
            second = transcripts.write_transcript(CONVERSATION, [{"role": "user", "content": "due", "created_at": "t"}])
            self.assertEqual(first, second)
            self.assertIn("due", second.read_text(encoding="utf-8"))
            self.assertNotIn("uno", second.read_text(encoding="utf-8"))
            self.assertEqual([p.name for p in second.parent.iterdir()], [second.name])


if __name__ == "__main__":
    unittest.main()
