"""Bounded memory checks: isolated contracts and explicitly disposable SQL tests."""
import os
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

from core.domain import episodes, memory, system_context, working_memory


class StoreFixture(unittest.TestCase):
    def connect(self, module):
        connection = MagicMock()

        @contextmanager
        def connect():
            yield connection

        self.enterContext(patch.object(module, "db_connection", connect))
        return connection


class OwnerContextTests(StoreFixture):
    def test_empty_context_has_explicit_defaults(self):
        connection = self.connect(system_context)
        connection.execute.return_value.fetchone.return_value = None
        result = system_context.get_system_context()
        self.assertEqual((result["content"], result["version"]), ("", 1))

    def test_stale_edit_does_not_write(self):
        connection = self.connect(system_context)
        connection.execute.return_value.fetchone.return_value = {"version": 3}
        with self.assertRaises(memory.MemoryConflict):
            system_context.update_system_context("stale", expected_version=2)
        self.assertEqual(connection.execute.call_count, 1)

    def test_edit_keeps_a_revision(self):
        connection = self.connect(system_context)
        row = {"version": 3, "content": "Owner", "metadata": {"source": "user"}}
        connection.execute.return_value.fetchone.side_effect = [{"version": 2}, row]
        self.enterContext(patch.object(system_context, "log_event"))
        self.assertEqual(system_context.update_system_context(" Owner ", expected_version=2), row)
        calls = connection.execute.call_args_list
        self.assertIn("system_context_versions", calls[-1].args[0])
        self.assertEqual(calls[-1].args[1][:2], (3, "Owner"))


class SemanticMemoryTests(StoreFixture):
    def test_write_records_revision_source_and_actor_classification(self):
        connection = self.connect(memory)
        row = {"id": uuid4(), "version": 1, "content": "Candidate", "assertion": "inference"}
        connection.execute.return_value.fetchone.side_effect = [None, row]
        self.enterContext(patch.object(memory, "log_event"))
        result = memory.save_memory(memory_type="note", key="candidate", content="Candidate",
                                    assertion="inference", confidence=0.6, editor="agent", source_ref="fixture")
        self.assertEqual(result["action"], "created")
        calls = connection.execute.call_args_list
        self.assertTrue(any("memory_versions" in c.args[0] for c in calls))
        self.assertTrue(any("memory_sources" in c.args[0] for c in calls))
        insert = next(c for c in calls if "INSERT INTO memories" in c.args[0])
        self.assertEqual(insert.args[1][-3:], ("inference", 0.6, "agent"))

    def test_invalid_facts_never_reach_storage(self):
        connection = self.connect(memory)
        for changes in ({"memory_type": "unknown"}, {"content": " "},
                        {"assertion": "certain"}, {"confidence": 1.1},
                        {"importance": 0}, {"expected_version": -1},
                        {"expires_at": "2020-01-01T00:00:00+00:00"},
                        {"editor": "agent", "assertion": "unclassified"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                memory.save_memory(**({"memory_type": "fact", "key": "x", "content": "fact"} | changes))
        connection.execute.assert_not_called()

    def test_empty_store_does_not_load_embedding_model(self):
        connection = self.connect(memory)
        connection.execute.return_value.fetchone.return_value = {"present": False}
        embed = self.enterContext(patch.object(memory, "embed_text"))
        self.assertEqual(memory.search_memories("question"), [])
        embed.assert_not_called()

    def test_embedding_unavailable_preserves_lexical_search_and_hides_vectors(self):
        connection = self.connect(memory)
        connection.execute.return_value.fetchone.return_value = {"present": True}
        connection.execute.return_value.fetchall.return_value = [{"key": "RAM", "content": "64 GB", "embedding": [1, 0]}]
        self.enterContext(patch.object(memory, "embed_text", return_value=(None, "offline")))
        self.enterContext(patch.object(memory, "log_event"))
        result = memory.search_memories("RAM", memory_type="fact", limit=999)
        self.assertEqual(result, [{"key": "RAM", "content": "64 GB"}])
        sql, params = connection.execute.call_args.args
        self.assertIn("ILIKE", sql)
        self.assertNotIn("<=>", sql)
        self.assertIn("expires_at > NOW()", sql)
        self.assertEqual(params[-1], 100)
        self.assertIn("fact", params)

    def test_semantic_query_checks_model_and_dimensions(self):
        connection = self.connect(memory)
        connection.execute.return_value.fetchone.return_value = {"present": True}
        connection.execute.return_value.fetchall.return_value = []
        self.enterContext(patch.object(memory, "embed_text", return_value=([1, 0], "fixture-model")))
        self.enterContext(patch.object(memory, "log_event"))
        memory.search_memories("memory")
        sql, params = connection.execute.call_args.args
        self.assertIn("embedding_model = %s", sql)
        self.assertIn("embedding_dimensions = %s", sql)
        self.assertIn("<=>", sql)
        self.assertIn("fixture-model", params)


class EpisodeTests(StoreFixture):
    def test_empty_episode_is_rejected(self):
        connection = self.connect(episodes)
        with self.assertRaises(ValueError):
            episodes.create_episode(title="x", summary=" ")
        connection.execute.assert_not_called()

    def test_episode_preserves_conversation_agent_and_unicode(self):
        connection = self.connect(episodes)
        self.enterContext(patch.object(episodes, "log_event"))
        cid = uuid4()
        episodes.create_episode(title=" evento ", summary=" attività verificata ",
                                conversation_id=str(cid), agent_id="supervisor", importance=99,
                                metadata={"fonte": "originale"})
        _, params = connection.execute.call_args.args
        self.assertEqual(params[1:7], (cid, "evento", "attività verificata", "conversation", "supervisor", 5))
        self.assertIn("originale", params[7])

    def test_list_is_bounded_and_newest_first(self):
        connection = self.connect(episodes)
        connection.execute.return_value.fetchall.return_value = []
        episodes.list_episodes(limit=999)
        sql, params = connection.execute.call_args.args
        self.assertIn("ORDER BY created_at DESC", sql)
        self.assertEqual(params, (200,))


@unittest.skipUnless(os.getenv("CORA_RUNTIME_TEST_DATABASE_URL"), "Requires disposable PostgreSQL+pgvector")
class MemoryStoresPostgresTests(unittest.TestCase):
    """Never registered as a production regression: these fixtures use a test DB."""
    def setUp(self):
        from core.infra import database
        # Match the existing test-DB opt-in and reject a mismatched database URL.
        if database.DATABASE_URL != os.environ["CORA_RUNTIME_TEST_DATABASE_URL"]:
            self.fail("CORA_DATABASE_URL must equal the disposable test database URL")
        with database.db_connection() as connection:
            connection.execute("TRUNCATE memories, episodes, working_memory CASCADE")

    def tearDown(self):
        from core.infra.database import close_pool
        close_pool()

    def test_lexical_search_expiry_filters_and_cascade(self):
        from core.infra.database import db_connection
        first = memory.save_memory(memory_type="fact", key="hardware", content="RAM 64 GB")
        memory.save_memory(memory_type="note", key="other", content="RAM for another project")
        with patch.object(memory, "embed_text", return_value=(None, None)):
            self.assertEqual([r["id"] for r in memory.search_memories("RAM", memory_type="fact")], [first["id"]])
        with db_connection() as connection:
            connection.execute("UPDATE memories SET expires_at=NOW()-INTERVAL '1 second' WHERE id=%s", (first["id"],))
        self.assertEqual(memory.search_memories(memory_type="fact"), [])
        self.assertEqual(len(memory.search_memories(memory_type="fact", include_expired=True)), 1)
        self.assertTrue(memory.delete_memory(str(first["id"])))
        self.assertEqual(memory.memory_history(str(first["id"])), [])
        with db_connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) AS n FROM memory_sources WHERE memory_id=%s", (first["id"],)).fetchone()["n"], 0)

    def test_hybrid_search_uses_real_vector_distance_without_ollama(self):
        from core.infra.database import db_connection
        a = memory.save_memory(memory_type="fact", key="a", content="configured capacity")
        b = memory.save_memory(memory_type="fact", key="b", content="unrelated subject")
        with db_connection() as connection:
            connection.execute("UPDATE memories SET embedding='[1,0]',embedding_model='fixture',embedding_dimensions=2 WHERE id=%s", (a["id"],))
            connection.execute("UPDATE memories SET embedding='[0,1]',embedding_model='fixture',embedding_dimensions=2 WHERE id=%s", (b["id"],))
        with patch.object(memory, "embed_text", return_value=([1, 0], "fixture")):
            self.assertEqual([r["id"] for r in memory.search_memories("capacity question")], [a["id"]])
        with patch.object(memory, "embed_text", return_value=([1, 0], "different-model")):
            self.assertEqual(memory.search_memories("capacity question"), [])

    def test_working_memory_update_is_scoped_and_expiry_is_enforced(self):
        from core.infra.database import db_connection
        working_memory.set_working_memory(agent_id="a", thread_id="one", state={"step": 1})
        working_memory.set_working_memory(agent_id="b", thread_id="one", state={"step": 2})
        working_memory.set_working_memory(agent_id="a", thread_id="one", state={"step": 3})
        rows = working_memory.list_working_memory()
        self.assertEqual({r["agent_id"]: r["state"]["step"] for r in rows}, {"a": 3, "b": 2})
        with db_connection() as connection:
            connection.execute("UPDATE working_memory SET expires_at=NOW()-INTERVAL '1 second' WHERE agent_id='a'")
        self.assertEqual([r["agent_id"] for r in working_memory.list_working_memory()], ["b"])
        self.assertTrue(working_memory.clear_working_memory(agent_id="b", thread_id="one"))
        self.assertEqual(working_memory.list_working_memory(), [])

    def test_episode_roundtrip_retains_source_and_conversation(self):
        from core.infra.database import db_connection
        cid = uuid4()
        with db_connection() as connection:
            connection.execute("INSERT INTO conversations(id) VALUES(%s)", (cid,))
        try:
            written = episodes.create_episode(title="Collaudo", summary="Fonte disponibile", conversation_id=str(cid),
                                               agent_id="supervisor", metadata={"source_ref": "fixture"})
            rows = episodes.list_episodes()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["id"], written["id"])
            self.assertEqual(rows[0]["conversation_id"], cid)
            self.assertEqual(rows[0]["metadata"]["source_ref"], "fixture")
        finally:
            with db_connection() as connection:
                connection.execute("DELETE FROM episodes WHERE conversation_id=%s", (cid,))
                connection.execute("DELETE FROM conversations WHERE id=%s", (cid,))
