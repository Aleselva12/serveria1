from __future__ import annotations

import os
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
    connection.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
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
