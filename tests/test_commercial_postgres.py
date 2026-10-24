"""Real SQL/API/Word integration against an explicitly disposable database."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from uuid import UUID, uuid4
from unittest.mock import patch

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core import commercial_notes, database
from core.audio_api import router
from tests.test_commercial_notes import sample


@unittest.skipUnless(os.getenv('CORA_RUNTIME_TEST_DATABASE_URL'), 'Requires disposable PostgreSQL+pgvector')
class CommercialPostgresTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'synthetic.docx'
        self.original = sample()
        self.target.write_bytes(self.original)
        self.patch = patch.object(commercial_notes, 'library_workspace_root', return_value=self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.env = patch.dict(os.environ, {'CORA_OWNER_TOKEN': 'synthetic-owner'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.ident = uuid4()
        with database.db_connection() as conn:
            conn.execute("INSERT INTO audio_records(id,title,name,source_path,transcript) VALUES(%s,'Synthetic','test.wav','synthetic','Client call')", (self.ident,))
        self.addCleanup(self.cleanup_rows)
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app, headers={'Authorization': 'Bearer synthetic-owner'})
        self.addCleanup(self.client.close)
        self.base = '/api/v1/audio/' + str(self.ident) + '/commercial'

    def cleanup_rows(self):
        with database.db_connection() as conn:
            conn.execute('DELETE FROM commercial_note_proposals WHERE audio_id=%s', (self.ident,))
            conn.execute('DELETE FROM audio_records WHERE id=%s', (self.ident,))
        database.close_pool()

    def propose(self, note='Explicit reviewed note'):
        response = self.client.get(self.base + '/customers', params={'query': 'LIDO TEST'})
        self.assertEqual(response.status_code, 200, response.text)
        match = response.json()['matches'][0]
        return self.client.post(self.base + '/proposals', json={
            'expected_audio_version': 1, 'selected': match, 'date': '24/10/2026', 'note': note})

    def resolve(self, proposal, approve=True):
        return self.client.post(self.base + '/proposals/' + proposal['id'] + '/resolve', json={'approve': approve})

    def test_real_api_approval_backup_and_replay(self):
        self.assertEqual(self.client.get(self.base + '/proposals', headers={'Authorization': ''}).status_code, 401)
        response = self.propose()
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual(self.propose().status_code, 409)
        proposal = response.json()
        self.assertEqual(self.resolve(proposal).json()['status'], 'approved')
        published = self.target.read_bytes()
        self.assertNotEqual(published, self.original)
        self.assertEqual((self.root / '.cora-commercial-backups' / (proposal['id'] + '.docx')).read_bytes(), self.original)
        self.assertEqual(self.resolve(proposal).status_code, 409)
        self.assertEqual(self.target.read_bytes(), published)
        self.assertEqual(self.propose().status_code, 409)

    def test_expired_pending_can_be_reviewed_again(self):
        first = self.propose().json()
        with database.db_connection() as conn:
            conn.execute("UPDATE commercial_note_proposals SET expires_at=NOW()-INTERVAL '1 second' WHERE id=%s", (UUID(first['id']),))
        self.assertEqual(self.propose().status_code, 201)
        self.assertEqual(self.resolve(first).status_code, 409)
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_rejection_and_changed_audio_never_write(self):
        rejected = self.propose().json()
        self.assertEqual(self.resolve(rejected, False).json()['status'], 'rejected')
        proposal = self.propose().json()
        with database.db_connection() as conn:
            conn.execute('UPDATE audio_records SET version=2 WHERE id=%s', (self.ident,))
        self.assertEqual(self.resolve(proposal).status_code, 409)
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_uncertain_write_is_persisted_and_never_replayed(self):
        proposal = self.propose().json()
        with patch.object(commercial_notes, '_publish', side_effect=OSError('synthetic failure')) as publish:
            self.assertEqual(self.resolve(proposal).status_code, 409)
            self.assertEqual(self.resolve(proposal).status_code, 409)
            self.assertEqual(publish.call_count, 1)
        self.assertEqual(self.client.get(self.base + '/proposals').json()[0]['status'], 'uncertain')
        self.assertEqual(self.propose().status_code, 409)

    def test_changed_word_fails_without_overwrite(self):
        proposal = self.propose().json()
        changed = self.original + b'changed'
        self.target.write_bytes(changed)
        self.assertEqual(self.resolve(proposal).status_code, 409)
        self.assertEqual(self.client.get(self.base + '/proposals').json()[0]['status'], 'failed')
        self.assertEqual(self.target.read_bytes(), changed)

    def test_concurrent_approvals_publish_only_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        proposal = self.propose().json()
        barrier = Barrier(2)
        def approve():
            barrier.wait(timeout=5)
            try:
                return commercial_notes.resolve_proposal(UUID(proposal['id']), True)['status']
            except ValueError:
                return 'already-claimed'
        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(lambda _: approve(), range(2)))
        self.assertCountEqual(outcomes, ['approved', 'already-claimed'])
        from docx import Document
        lines = [paragraph.text for paragraph in Document(self.target).paragraphs]
        self.assertEqual(lines.count('Explicit reviewed note'), 1)
        self.assertEqual(len(list((self.root / '.cora-commercial-backups').glob('*.docx'))), 1)

    def test_0005_upgrade_to_0006_and_repeated_installer(self):
        """Install 0001-0005, preserve an audio row, upgrade and rerun."""
        name = 'pr84_' + uuid4().hex
        url = os.environ['CORA_RUNTIME_TEST_DATABASE_URL']
        with psycopg.connect(url, autocommit=True) as admin:
            admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            try:
                from psycopg.conninfo import make_conninfo
                with psycopg.connect(make_conninfo(url, dbname=name), row_factory=dict_row) as conn:
                    migration_root = self.root / 'migrations'
                    migration_root.mkdir()
                    for path in database.MIGRATIONS_ROOT.glob('*.sql'):
                        if path.name < '0006':
                            shutil.copyfile(path, migration_root / path.name)
                    with patch.object(database, 'MIGRATIONS_ROOT', migration_root), patch.object(database, '_schema_ready', False):
                        database._ensure_schema(conn)
                    self.assertEqual(conn.execute("SELECT count(*) AS n FROM cora_schema_migrations").fetchone()['n'], 5)
                    audio = uuid4()
                    conn.execute("INSERT INTO audio_records(id,title,name,source_path) VALUES(%s,'Preserved','old.wav','synthetic')", (audio,))
                    conn.commit()
                    shutil.copyfile(database.MIGRATIONS_ROOT / '0006_commercial_note_proposals.sql', migration_root / '0006_commercial_note_proposals.sql')
                    for _ in range(2):
                        with patch.object(database, 'MIGRATIONS_ROOT', migration_root), patch.object(database, '_schema_ready', False):
                            database._ensure_schema(conn)
                    self.assertEqual(conn.execute('SELECT count(*) AS n FROM cora_schema_migrations').fetchone()['n'], 6)
                    self.assertEqual(conn.execute('SELECT title FROM audio_records WHERE id=%s', (audio,)).fetchone()['title'], 'Preserved')
                    self.assertIsNotNone(conn.execute("SELECT to_regclass('commercial_note_prevent_replay') AS name").fetchone()['name'])
            finally:
                admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
