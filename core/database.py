from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("CORA_DATABASE_URL", "").strip()
SCHEMA_FILE = PROJECT_ROOT / "database" / "schema.sql"
_schema_ready = False
_schema_lock = threading.Lock()
_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def database_configured() -> bool:
    return bool(DATABASE_URL)


def _require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError(
            "CORA_DATABASE_URL non configurato. Cora richiede PostgreSQL + pgvector."
        )
    return DATABASE_URL


def _pool_sizes() -> tuple[int, int]:
    try:
        minimum = max(1, int(os.getenv("CORA_DB_POOL_MIN", "1")))
        maximum = max(minimum, int(os.getenv("CORA_DB_POOL_MAX", "6")))
    except ValueError as error:
        raise RuntimeError("CORA_DB_POOL_MIN/MAX non validi.") from error
    return minimum, maximum


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            minimum, maximum = _pool_sizes()
            _pool = ConnectionPool(
                conninfo=_require_database_url(),
                min_size=minimum,
                max_size=maximum,
                kwargs={"row_factory": dict_row},
                open=True,
            )
    return _pool


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None


def _ensure_schema(connection: Connection) -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        if not SCHEMA_FILE.exists():
            raise RuntimeError(f"Schema PostgreSQL non trovato: {SCHEMA_FILE}")
        connection.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
        connection.commit()
        _schema_ready = True


@contextmanager
def db_connection(*, ensure_schema: bool = True) -> Iterator[Connection]:
    pool = _get_pool()
    with pool.connection() as connection:
        if ensure_schema:
            _ensure_schema(connection)
        # pgvector registration is cheap and tied to the live psycopg connection.
        register_vector(connection)
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise


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
            "pool": {
                "min": _pool_sizes()[0],
                "max": _pool_sizes()[1],
            },
        }
    except Exception as error:
        return {
            "configured": True,
            "reachable": False,
            "backend": "postgresql+pgvector",
            "error": f"{type(error).__name__}: {error}",
        }
