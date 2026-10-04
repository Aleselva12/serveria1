from __future__ import annotations

import json
from typing import Any

from core.database import db_connection
from core.logging import log_event


def get_system_context() -> dict[str, Any]:
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
    return dict(result)


def update_system_context(
    content: str,
    *,
    metadata: dict[str, Any] | None = None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    normalized = content.strip()
    with db_connection() as connection:
        previous = connection.execute('SELECT version FROM system_context WHERE id=1 FOR UPDATE').fetchone()
        if expected_version is not None and (previous['version'] if previous else 0) != expected_version:
            from core.memory import MemoryConflict
            raise MemoryConflict('Contesto modificato altrove: rileggi la versione corrente.')
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
        connection.execute('INSERT INTO system_context_versions (version,content,metadata) VALUES (%s,%s,%s::jsonb)',
                           (row['version'],row['content'],json.dumps(row['metadata'],ensure_ascii=False)))
        connection.commit()

    log_event(
        "system_context_update",
        component="system_context",
        data={"version": row["version"], "content_chars": len(normalized)},
    )
    return row
