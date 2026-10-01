from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("CORA_DATABASE_URL", "").strip()
SCHEMA_FILE = PROJECT_ROOT / "database" / "schema.sql"
_schema_ready = False


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


@contextmanager
def db_connection(*, ensure_schema: bool = True) -> Iterator[psycopg.Connection]:
    connection = psycopg.connect(_require_database_url(), row_factory=dict_row)
    try:
        if ensure_schema:
            _ensure_schema(connection)
        register_vector(connection)
        yield connection
    finally:
        connection.close()


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
