from __future__ import annotations

import os
import hashlib
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("CORA_DATABASE_URL", "").strip()
SCHEMA_FILE = PROJECT_ROOT / "database" / "schema.sql"
MIGRATIONS_ROOT = PROJECT_ROOT / 'database' / 'migrations'
_schema_ready = False
_schema_lock = threading.Lock()
_pool_lock = threading.Lock()
_pool = None


def database_configured() -> bool:
    return bool(DATABASE_URL)


def _require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError(
            "CORA_DATABASE_URL non configurato. Cora richiede PostgreSQL + pgvector."
        )
    return DATABASE_URL


def _ensure_schema(connection: psycopg.Connection) -> None:
    global _schema_ready
    if _schema_ready:
        return
    if not SCHEMA_FILE.exists():
        raise RuntimeError(f"Schema PostgreSQL non trovato: {SCHEMA_FILE}")
    # One installer at a time, even across processes/host provisioning commands.
    connection.execute('SELECT pg_advisory_xact_lock(709241001)')
    connection.execute('''CREATE TABLE IF NOT EXISTS cora_schema_migrations (
        version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
    files = [('0001_baseline',SCHEMA_FILE)]
    files += [(path.stem,path) for path in sorted(MIGRATIONS_ROOT.glob('[0-9][0-9][0-9][0-9]_*.sql'))]
    versions = [version for version,_ in files]
    if len(versions)!=len({version[:4] for version in versions}) or any(version[:4]<='0001' for version,_ in files[1:]):
        raise RuntimeError('Migration versions must be unique and follow the baseline')
    applied = {row['version']:row['checksum'] for row in connection.execute('SELECT version,checksum FROM cora_schema_migrations').fetchall()}
    if set(applied)-set(versions): raise RuntimeError('Database schema is newer than this code; rollback requires a matching backup')
    if applied and any(version not in applied and version<max(applied) for version in versions):
        raise RuntimeError('New migrations must follow every applied version')
    for version,path in files:
        # Git may check out CRLF on the test PC and LF on Debian.
        content=path.read_bytes().replace(b'\r\n',b'\n')
        checksum=hashlib.sha256(content).hexdigest()
        if version in applied:
            if applied[version]!=checksum:raise RuntimeError('Applied migration changed: '+version)
            continue
        connection.execute(content.decode('utf-8'))
        connection.execute('INSERT INTO cora_schema_migrations(version,checksum) VALUES(%s,%s)',(version,checksum))
    connection.commit()
    _schema_ready = True


def get_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ConnectionPool(_require_database_url(), min_size=1,
                max_size=max(1, int(os.getenv("CORA_DB_POOL_SIZE", "4"))),
                timeout=float(os.getenv("CORA_DB_POOL_TIMEOUT", "10")), max_waiting=16,
                kwargs={"row_factory": dict_row, "connect_timeout": 5,
                        "prepare_threshold": None if os.getenv("CORA_DB_PREPARE_THRESHOLD", "5") == "none" else int(os.getenv("CORA_DB_PREPARE_THRESHOLD", "5")),
                        "options": "-c statement_timeout=30000 -c lock_timeout=5000"}, open=True)
        return _pool


def close_pool():
    global _pool, _schema_ready
    with _pool_lock:
        if _pool is not None:
            _pool.close()
        _pool = None
        _schema_ready = False


@contextmanager
def db_connection(*, ensure_schema: bool = True) -> Iterator[psycopg.Connection]:
    with get_pool().connection() as connection:
        if ensure_schema:
            with _schema_lock:
                _ensure_schema(connection)
        if not getattr(connection, "_cora_vector_ready", False):
            register_vector(connection)
            connection._cora_vector_ready = True
        yield connection


def pool_stats():
    return _pool.get_stats() if _pool is not None else {"pool_size": 0}


def database_status() -> dict:
    if not database_configured():
        return {
            "configured": False,
            "reachable": False,
            "backend": "postgresql+pgvector",
        }
    try:
        with db_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    current_database() AS database,
                    EXISTS (
                        SELECT 1
                        FROM pg_extension
                        WHERE extname = 'vector'
                    ) AS pgvector
                """
            ).fetchone()
        return {
            "configured": True,
            "reachable": True,
            "backend": "postgresql+pgvector",
            "database": row["database"],
            "pgvector": bool(row["pgvector"]),
        }
    except Exception as error:
        return {
            "configured": True,
            "reachable": False,
            "backend": "postgresql+pgvector",
            "error": f"{type(error).__name__}: {error}",
        }
