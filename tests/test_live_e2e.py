"""Live E2E checks, exercised here on fakes and disposable resources."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from core.verify import live_e2e


class GmailReadTests(unittest.TestCase):
    def run_check(self, linked=("a", "b"), profiles=None, error=None):
        accounts = {"a": "uno@example.com", "b": "due@example.com"}
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        for key in linked:
            Path(folder.name, key).write_text("{}")
        services = {}
        for key, email in accounts.items():
            service = MagicMock()
            users = service.users.return_value
            users.getProfile.return_value.execute.return_value = {"emailAddress": (profiles or {}).get(key, email)}
            users.messages.return_value.list.return_value.execute.return_value = {"messages": [{"id": "m1"}]}
            users.messages.return_value.get.return_value.execute.return_value = {"id": "m1"}
            services[key] = service
        def service(key):
            if error and key == "b":
                raise error
            return services[key]
        with patch("core.domain.mail.ACCOUNTS", accounts), \
                patch("core.domain.mail.token_path", lambda key: Path(folder.name, key)), \
                patch("core.domain.mail.service", service):
            return live_e2e.gmail_read(), services

    def test_both_accounts_read_only_without_opening_messages(self):
        (status, detail), services = self.run_check()
        self.assertEqual(status, "pass")
        self.assertIn("uno: lettura riuscita; due: lettura riuscita", detail)
        messages = services["a"].users.return_value.messages.return_value
        self.assertEqual(messages.get.call_args.kwargs["format"], "minimal")
        self.assertEqual(messages.list.call_args.kwargs["maxResults"], 1)
        for forbidden in ("modify", "trash", "delete", "send", "batchModify"):
            getattr(messages, forbidden).assert_not_called()
        services["a"].users.return_value.drafts.assert_not_called()

    def test_token_of_another_account_or_revoked_authorisation_fails(self):
        self.assertEqual(self.run_check(profiles={"b": "altro@example.com"})[0][0], "fail")
        from google.auth.exceptions import RefreshError
        (status, detail), _ = self.run_check(error=RefreshError("revoked"))
        self.assertEqual(status, "fail")
        self.assertIn("ricollegare dalla pagina Mail", detail)

    def test_unlinked_accounts_are_reported_not_failed(self):
        self.assertEqual(self.run_check(linked=())[0][0], "unknown")
        (status, detail), _ = self.run_check(linked=("a",))
        self.assertEqual(status, "warn")
        self.assertIn("due: non collegato", detail)


class FilesLiveTests(unittest.TestCase):
    def roots(self, writable=True, nas=True):
        data = tempfile.TemporaryDirectory()
        drive = tempfile.TemporaryDirectory()
        self.addCleanup(data.cleanup)
        self.addCleanup(drive.cleanup)
        Path(drive.name, "documento.txt").write_text("x")
        roots = [{"id": "cora", "label": "Dati Cora", "path": data.name, "writable": writable}]
        if nas:
            roots.append({"id": "drive", "label": "Drive NAS", "path": drive.name, "writable": True})
        return Path(data.name), Path(drive.name), roots

    def test_full_cycle_on_disk_leaves_nothing_behind_and_never_writes_the_nas(self):
        data, drive, roots = self.roots()
        with patch("core.domain.server_files.roots", return_value=roots):
            status, detail = live_e2e.files_live()
        self.assertEqual(status, "pass", detail)
        self.assertIn("NAS leggibile (1 elementi", detail)
        # Only the app's own reserved areas (.cora-staging, .cora-trash) may remain, and empty of our files.
        self.assertEqual([p.name for p in data.iterdir() if not p.name.startswith(".cora-")], [])
        self.assertEqual(list((data / ".cora-trash").iterdir()), [])
        self.assertEqual([p.name for p in drive.iterdir()], ["documento.txt"])

    def test_missing_or_read_only_resource_is_not_a_failure(self):
        _, _, roots = self.roots(writable=False)
        with patch("core.domain.server_files.roots", return_value=roots):
            self.assertEqual(live_e2e.files_live()[0], "unknown")

    def test_an_unreadable_nas_fails(self):
        data, drive, roots = self.roots()
        roots[1]["path"] = str(drive / "missing")
        with patch("core.domain.server_files.roots", return_value=roots):
            status, detail = live_e2e.files_live()
        self.assertEqual(status, "fail")
        self.assertIn("NAS", detail)
        self.assertEqual([p.name for p in data.iterdir() if not p.name.startswith(".cora-")], [])


@unittest.skipUnless(os.getenv("CORA_RUNTIME_TEST_DATABASE_URL"), "Requires disposable PostgreSQL+pgvector")
class WordLivePostgresTests(unittest.TestCase):
    def test_real_proposal_flow_writes_once_and_cleans_up(self):
        from core.infra.database import db_connection
        with tempfile.TemporaryDirectory() as folder, \
                patch("core.infra.file_paths.library_workspace_root", return_value=Path(folder)), \
                patch("core.domain.commercial_notes.library_workspace_root", return_value=Path(folder)):
            status, detail = live_e2e.word_live()
            leftovers = [p for p in Path(folder).rglob("*") if p.is_file()]
        self.assertEqual(status, "pass", detail)
        self.assertEqual(leftovers, [])
        with db_connection() as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM audio_records WHERE source_path='collaudo'").fetchone())

    def test_a_failure_still_cleans_up(self):
        from core.infra.database import db_connection
        with tempfile.TemporaryDirectory() as folder, \
                patch("core.infra.file_paths.library_workspace_root", return_value=Path(folder)), \
                patch("core.domain.commercial_notes.library_workspace_root", return_value=Path(folder)), \
                patch("core.domain.commercial_notes._publish", side_effect=ValueError("synthetic")):
            status, _ = live_e2e.word_live()
            leftovers = [p for p in Path(folder).rglob("*") if p.is_file()]
        self.assertEqual(status, "fail")
        self.assertEqual(leftovers, [])
        with db_connection() as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM commercial_note_proposals p JOIN audio_records a "
                                           "ON a.id=p.audio_id WHERE a.source_path='collaudo'").fetchone())


class RegistrationTests(unittest.TestCase):
    def test_live_checks_run_in_the_collaudo_with_the_real_environment(self):
        from core.health_catalog import CATALOG
        from deploy import verify_nodes
        for key in live_e2e.LIVE:
            self.assertIn(key, verify_nodes.available_checks())
            self.assertEqual(CATALOG[key]["kind"], "e2e")
        with patch.dict(live_e2e.LIVE, {"gmail_read_e2e": lambda: ("pass", "ok")}):
            self.assertEqual(verify_nodes._action("gmail_read_e2e", str(uuid4())), {"status": "pass", "detail": "ok"})
