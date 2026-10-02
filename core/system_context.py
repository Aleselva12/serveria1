from __future__ import annotations

import json
import threading
from typing import Any

from core.database import db_connection
from core.logging import log_event


_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, Any] | None = None


def get_system_context() -> dict[str, Any]:
    global _CACHE
    with _CACHE_LOCK:
        if _CACHE is not None:
            return dict(_CACHE)

    with db_connection() as connection:
        row = connection.execute(
            """
            SELECT id, content, version, updated_at, metadata
            FROM system_context
            WHERE id = 1
            """
        ).fetchone()
    result = row or {
        "id": 1,
        "content": "",
        "version": 1,
        "updated_at": None,
        "metadata": {},
    }
    with _CACHE_LOCK:
        _CACHE = dict(result)
    return dict(result)


def update_system_context(
    content: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = content.strip()
    with db_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO system_context (id, content, version, updated_at, metadata)
            VALUES (1, %s, 1, NOW(), %s::jsonb)
            ON CONFLICT (id)
            DO UPDATE SET
                content = EXCLUDED.content,
                version = system_context.version + 1,
                updated_at = NOW(),
                metadata = EXCLUDED.metadata
            RETURNING id, content, version, updated_at, metadata
            """,
            (normalized, json.dumps(metadata or {}, ensure_ascii=False)),
        ).fetchone()
        connection.commit()

    global _CACHE
    with _CACHE_LOCK:
        _CACHE = dict(row)

    log_event(
        "system_context_update",
        component="system_context",
        data={"version": row["version"], "content_chars": len(normalized)},
    )
    return row
