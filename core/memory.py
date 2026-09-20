from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.logging import log_event


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEMORY_ROOT = Path(
    os.getenv("CORA_MEMORY_ROOT", str(PROJECT_ROOT / "data"))
).expanduser().resolve()
MEMORY_DB = Path(
    os.getenv("CORA_MEMORY_DB", str(MEMORY_ROOT / "cora_memory.sqlite3"))
).expanduser().resolve()

ALLOWED_MEMORY_TYPES = {
    "fact",
    "preference",
    "person",
    "project",
    "decision",
    "note",
    "task_context",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(MEMORY_DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(connection)
    return connection


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            memory_type TEXT NOT NULL,
            key TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL,
            importance INTEGER NOT NULL DEFAULT 3,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            expires_at TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE(memory_type, key)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key)"
    )
    connection.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    try:
        result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
    except json.JSONDecodeError:
        result["metadata"] = {}
        result.pop("metadata_json", None)
    return result


def save_memory(
    *,
    memory_type: str,
    key: str,
    content: str,
    source: str = "user_explicit",
    importance: int = 3,
    expires_at: str | None = None,
    metadata: dict[str, Any] | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Create or update one persistent memory, identified by type + key."""
    normalized_type = memory_type.strip().lower()
    if normalized_type not in ALLOWED_MEMORY_TYPES:
        raise ValueError(
            "memory_type non valido. Valori ammessi: "
            + ", ".join(sorted(ALLOWED_MEMORY_TYPES))
        )

    normalized_key = key.strip()
    normalized_content = content.strip()
    if not normalized_key or not normalized_content:
        raise ValueError("key e content non possono essere vuoti.")

    importance = max(1, min(int(importance), 5))
    now = _utc_now()

    with _connect() as connection:
        existing = connection.execute(
            "SELECT id, created_at FROM memories WHERE memory_type = ? AND key = ?",
            (normalized_type, normalized_key),
        ).fetchone()

        if existing:
            memory_id = existing["id"]
            created_at = existing["created_at"]
            connection.execute(
                """
                UPDATE memories
                SET content = ?, source = ?, importance = ?, updated_at = ?,
                    expires_at = ?, metadata_json = ?
                WHERE id = ?
                """,
                (
                    normalized_content,
                    source,
                    importance,
                    now,
                    expires_at,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    memory_id,
                ),
            )
            action = "updated"
        else:
            memory_id = str(uuid.uuid4())
            created_at = now
            connection.execute(
                """
                INSERT INTO memories (
                    id, memory_type, key, content, source, importance,
                    created_at, updated_at, expires_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    normalized_type,
                    normalized_key,
                    normalized_content,
                    source,
                    importance,
                    created_at,
                    now,
                    expires_at,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            action = "created"

        connection.commit()

    result = {
        "id": memory_id,
        "memory_type": normalized_type,
        "key": normalized_key,
        "content": normalized_content,
        "source": source,
        "importance": importance,
        "created_at": created_at,
        "updated_at": now,
        "expires_at": expires_at,
        "metadata": metadata or {},
        "action": action,
    }
    log_event(
        "memory_write",
        component="memory_store",
        thread_id=thread_id,
        data={
            "memory_id": memory_id,
            "memory_type": normalized_type,
            "action": action,
        },
    )
    return result


def search_memories(
    query: str = "",
    *,
    memory_type: str = "",
    limit: int = 20,
    thread_id: str | None = None,
) -> list[dict[str, Any]]:
    """Search persistent memories using a simple local lexical query."""
    limit = max(1, min(int(limit), 100))
    clauses = ["(expires_at IS NULL OR expires_at > ?)"]
    params: list[Any] = [_utc_now()]

    normalized_query = query.strip()
    normalized_type = memory_type.strip().lower()

    if normalized_type:
        if normalized_type not in ALLOWED_MEMORY_TYPES:
            raise ValueError(
                "memory_type non valido. Valori ammessi: "
                + ", ".join(sorted(ALLOWED_MEMORY_TYPES))
            )
        clauses.append("memory_type = ?")
        params.append(normalized_type)

    if normalized_query:
        clauses.append("(key LIKE ? OR content LIKE ?)")
        pattern = f"%{normalized_query}%"
        params.extend([pattern, pattern])

    params.append(limit)
    sql = f"""
        SELECT *
        FROM memories
        WHERE {' AND '.join(clauses)}
        ORDER BY importance DESC, updated_at DESC
        LIMIT ?
    """

    with _connect() as connection:
        rows = connection.execute(sql, params).fetchall()

    results = [_row_to_dict(row) for row in rows]
    log_event(
        "memory_read",
        component="memory_store",
        thread_id=thread_id,
        data={
            "query_chars": len(normalized_query),
            "memory_type": normalized_type or None,
            "result_count": len(results),
        },
    )
    return results


def delete_memory(memory_id: str, *, thread_id: str | None = None) -> bool:
    """Delete one memory by id."""
    with _connect() as connection:
        result = connection.execute(
            "DELETE FROM memories WHERE id = ?",
            (memory_id.strip(),),
        )
        connection.commit()
        deleted = result.rowcount > 0

    log_event(
        "memory_delete",
        component="memory_store",
        thread_id=thread_id,
        data={"memory_id": memory_id, "deleted": deleted},
    )
    return deleted


def memory_stats() -> dict[str, Any]:
    with _connect() as connection:
        total = connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        by_type_rows = connection.execute(
            "SELECT memory_type, COUNT(*) AS count FROM memories GROUP BY memory_type"
        ).fetchall()

    return {
        "database": str(MEMORY_DB),
        "total": total,
        "by_type": {row["memory_type"]: row["count"] for row in by_type_rows},
    }
