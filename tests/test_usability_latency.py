import json
import unittest
from unittest.mock import patch, MagicMock
from core import embeddings
from core.auth import setup_if_needed
from core.background_embeddings import index_pending_once

class LatencyUnitTests(unittest.TestCase):
    def test_embedding_query_cache_and_specific_timeout(self):
        embeddings._cache.clear()
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps({'embeddings':[[1.0,2.0]]}).encode()
        with patch.object(embeddings,'EMBEDDING_MODEL','local-test'), patch.object(embeddings,'urlopen',return_value=response) as request:
            self.assertEqual(embeddings.embed_text('query',timeout=5,cached=True),([1.0,2.0],'local-test'))
            self.assertEqual(embeddings.embed_text('query',timeout=5,cached=True),([1.0,2.0],'local-test'))
            request.assert_called_once();self.assertEqual(request.call_args.kwargs['timeout'],5)
        embeddings._cache.clear()

    def test_background_does_not_acquire_slot_after_recent_foreground_work(self):
        import time
        from core.background_embeddings import runtime
        with patch.object(runtime,'last_foreground',time.monotonic()),patch('core.background_embeddings.db_connection') as db:
            self.assertFalse(index_pending_once());db.assert_not_called()
        self.assertTrue(runtime.slot.acquire(blocking=False));runtime.slot.release()

    def test_existing_owner_is_never_prompted_or_reset(self):
        db=MagicMock();db.__enter__.return_value.execute.return_value.fetchone.return_value={'id':'existing'}
        with patch('core.auth.db_connection',return_value=db),patch('core.auth.interactive_provision') as prompt:
            setup_if_needed();prompt.assert_not_called()

    def test_invalid_batch_does_not_mismatch_message_vectors(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=b'{"embeddings":[[1.0]]}'
        with patch.object(embeddings,'EMBEDDING_MODEL','test'),patch.object(embeddings,'urlopen',return_value=response):
            self.assertEqual(embeddings.embed_batch(['one','two']),[None,None])
