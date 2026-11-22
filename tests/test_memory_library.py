import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import ValidationError

from core.domain import memory_library as library
from core.domain.episodes import create_episode
from core.domain.memory import MemoryConflict
from core.infra import database
from core.infra.run_lifecycle import create_run, transition_run
from deploy.verify_nodes import run


def card(scope, slug, **changes):
    fields = dict(title="Piano ServerIa2", description="Decisione di progetto",
                  content="Decisione originale", kind="decision")
    return library.CardCreate(scope=scope, slug=slug, **{**fields, **changes})


class MemoryLibraryContractTests(unittest.TestCase):
    def test_approved_claim_needs_evidence_and_valid_dates(self):
        scope = "azienda/serveria2"
        with self.assertRaises(ValidationError):
            card(scope, "decisione", assertion="observation", state="approved")
        with self.assertRaises(ValidationError):
            card(scope, "decisione", valid_from="2026-01-01T12:00")
        with self.assertRaises(ValidationError):
            card("azienda/../altro", "decisione")
        self.assertEqual(card(scope, "decisione", assertion="inference").state, "draft")
        self.assertEqual(library.visible_scopes(scope), ["global", "azienda", scope])

    def test_run_check_always_cleans_generated_scope(self):
        responses = [{"status": "pass"}, {"status": "fail"}, {"status": "pass"}]
        with (
            patch.dict(os.environ, {"CORA_DATABASE_URL": "configured"}),
            patch("deploy.verify_nodes._child", side_effect=responses) as child,
        ):
            self.assertEqual(run("memory_library_e2e")["status"], "fail")
        self.assertEqual([call.args[0] for call in child.call_args_list],
                         ["library_write", "library_read", "library_cleanup"])
        self.assertEqual(len({call.args[1] for call in child.call_args_list}), 1)


@unittest.skipUnless(os.getenv("CORA_RUNTIME_TEST_DATABASE_URL"), "Requires disposable PostgreSQL+pgvector")
class MemoryLibraryPostgresTests(unittest.TestCase):
    def setUp(self):
        if database.DATABASE_URL != os.environ["CORA_RUNTIME_TEST_DATABASE_URL"]:
            self.fail("CORA_DATABASE_URL must equal the disposable test database URL")
        self.root = f"test-library-{uuid4()}"
        self.project = self.root + "/serveria2"
        self.other = self.root + "/sibling"
        self.addCleanup(self.remove_cards)

    def remove_cards(self):
        with database.db_connection() as conn:
            conn.execute("DELETE FROM memory_cards WHERE scope = ANY(%s)",
                         ([self.root, self.project, self.other],))

    def test_revision_scope_links_and_export(self):
        parent = library.save_card(card(self.root, "shared"))
        unrelated = library.save_card(card(self.other, "shared"))
        scoped = library.save_card(card(self.project, "shared"))
        with self.assertRaises(MemoryConflict):
            library.save_card(card(self.project, "shared"))
        with self.assertRaises(ValueError):
            library.save_card(card(self.project, "wrong-link", relations=[
                {"kind": "contradicts", "target_id": unrelated["id"]},
            ]))
        self.assertEqual([item["id"] for item in library.list_cards(self.project)], [scoped["id"]])
        self.assertIn(self.root, library.list_scopes(after=self.root[:-1], limit=10))
        revised = library.CardEdit(
            expected_version=1, **{**scoped["document"], "content": "Decisione corretta", "state": "approved",
                                   "relations": [{"kind": "supersedes", "target_id": parent["id"]}]},
        )
        saved = library.save_card(revised, scoped["id"])
        self.assertEqual(saved["version"], 2)
        with self.assertRaises(MemoryConflict):
            library.save_card(revised, scoped["id"])
        self.assertEqual(library.get_card(scoped["id"], 1)["document"]["content"], "Decisione originale")
        self.assertEqual(library.list_cards(self.project, "corretta")[0]["id"], scoped["id"])
        self.assertEqual(library.export_cards(self.project), [saved])
        self.assertFalse(library.export_cards(self.root))
        self.assertFalse(library.export_cards(self.project, after="shared"))
        archived = library.CardEdit(expected_version=2, **{**saved["document"], "state": "archived"})
        library.save_card(archived, scoped["id"])
        self.assertFalse(library.export_cards(self.project))

    def test_import_is_atomic_and_never_overwrites_existing(self):
        existing = library.save_card(card(self.project, "z-keep"))
        bundle = library.StarterDrafts(
            format="serveria-memory-drafts-v1",
            cards=[card(self.project, "a-new"), card(self.project, "z-keep")],
        )
        with self.assertRaises(MemoryConflict):
            library.import_drafts(bundle)
        self.assertEqual(library.get_card(existing["id"]), existing)
        self.assertEqual([row["slug"] for row in library.list_cards(self.project)], ["z-keep"])
        imported = library.import_drafts(library.StarterDrafts(
            format="serveria-memory-drafts-v1", cards=[card(self.project, "a-new")],
        ))
        self.assertEqual(imported[0]["document"]["state"], "draft")
        with self.assertRaises(ValidationError):
            library.StarterDrafts(format="serveria-memory-drafts-v1",
                                  cards=[card(self.project, "bad", state="approved")])

    def test_evidence_is_resolvable_and_exports_exclude_expired(self):
        from core.api.memory_api import run_evidence

        thread_id = uuid4()
        with database.db_connection() as conn:
            conn.execute("INSERT INTO conversations (id) VALUES (%s)", (thread_id,))
        self.addCleanup(self.remove_conversation, thread_id)
        source = create_run(thread_id=str(thread_id))
        run_id = source["id"]
        self.addCleanup(self.remove_run, run_id)
        transition_run(str(run_id), "running")
        transition_run(str(run_id), "completed")
        with database.db_connection() as conn:
            for message, metadata in (
                ("Richiesta originale", {"run_id": str(run_id)}),
                ("Richiesta di un altro run", {"run_id": str(uuid4())}),
                ("Messaggio storico", {}),
            ):
                conn.execute(
                    """INSERT INTO messages (id, conversation_id, role, content, metadata)
                       VALUES (%s, %s, 'user', %s, %s)""",
                    (uuid4(), thread_id, message, Jsonb(metadata)),
                )
        episode = create_episode(title="Decisione", summary="Resoconto derivato",
                                 conversation_id=str(thread_id), metadata={"run_id": str(run_id)})
        with self.assertRaises(ValueError):
            library.save_card(card(self.project, "missing", source_runs=[uuid4()]))
        current = library.save_card(card(self.project, "current", source_runs=[run_id],
                                         state="approved", assertion="observation"))
        library.save_card(card(self.project, "expired", state="approved",
                               valid_until="2000-01-01T00:00:00Z"))
        evidence = run_evidence(run_id, after=0, limit=10)
        self.assertEqual(current["document"]["source_runs"], [str(evidence["run_id"])])
        self.assertEqual(evidence["report"]["status"], "completed")
        self.assertTrue(evidence["events"])
        self.assertEqual([row["content"] for row in evidence["messages"]], ["Richiesta originale"])
        self.assertEqual(evidence["report"]["episode"]["id"], episode["id"])
        self.assertEqual(library.export_cards(self.project), [current])

    def remove_run(self, run_id):
        with database.db_connection() as conn:
            conn.execute("DELETE FROM domain_events WHERE root_run_id = %s", (run_id,))
            conn.execute("DELETE FROM runtime_runs WHERE id = %s", (run_id,))

    def remove_conversation(self, thread_id):
        with database.db_connection() as conn:
            conn.execute("DELETE FROM episodes WHERE conversation_id = %s", (thread_id,))
            conn.execute("DELETE FROM conversations WHERE id = %s", (thread_id,))
