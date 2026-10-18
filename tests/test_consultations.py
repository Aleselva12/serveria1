import os
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from uuid import uuid4

from core import consultations


class ConsultationTests(unittest.TestCase):
    def test_failed_history_write_never_turns_completed_tool_into_retry(self):
        before=consultations._failures
        run=SimpleNamespace(thread_id=str(uuid4()),id=str(uuid4()))
        with patch.object(consultations,'database_configured',return_value=True),patch.object(consultations,'db_connection',side_effect=OSError('private error')):
            consultations.record('tool','library_read','ok',run=run)
        self.assertEqual(consultations._failures,before+1)

    def test_non_chat_runs_do_not_create_or_recreate_conversations(self):
        run=SimpleNamespace(thread_id='approval:internal',id=str(uuid4()))
        with patch.object(consultations,'database_configured',return_value=True),patch.object(consultations,'db_connection') as conn:
            consultations.record('tool','test','ok',run=run)
        conn.assert_not_called()

    def test_roadmap_render_is_current_and_decisions_remain_explicit(self):
        import json
        from deploy.render_roadmap import ROOT,render
        rows=json.loads((ROOT/'docs/roadmap.json').read_text(encoding='utf-8'))
        self.assertEqual(len(rows),17)
        self.assertEqual(rows[12]['state'],'Escluso')
        self.assertIn('causa utente',rows[5]['state'])
        self.assertEqual((ROOT/'17 passi.txt').read_text(encoding='utf-8'),render())


@unittest.skipUnless(os.getenv('CORA_RUNTIME_TEST_DATABASE_URL'),'Requires disposable PostgreSQL')
class ConsultationPostgresTests(unittest.TestCase):
    def test_pagination_isolation_and_conversation_deletion(self):
        from core.chat_store import ensure_conversation
        from core.database import db_connection
        first,second=uuid4(),uuid4()
        ensure_conversation(str(first));ensure_conversation(str(second))
        run=SimpleNamespace(thread_id=str(first),id=str(uuid4()))
        try:
            for i in range(4):consultations.record('file',f'private-{i}.txt','read',run=run)
            page=consultations.read(first,limit=2)
            self.assertEqual(len(page['items']),2)
            self.assertIsNotNone(page['next_before'])
            older=consultations.read(first,before=page['next_before'],limit=2)
            self.assertIsNone(older['next_before'])
            self.assertFalse({x['id'] for x in page['items']} & {x['id'] for x in older['items']})
            self.assertEqual(consultations.read(second)['items'],[])
            with db_connection() as conn:conn.execute('DELETE FROM conversations WHERE id=%s',(first,))
            self.assertEqual(consultations.read(first)['items'],[])
        finally:
            with db_connection() as conn:conn.execute('DELETE FROM conversations WHERE id IN (%s,%s)',(first,second))
