from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from core.database import db_connection


DEFAULT_TTL_MINUTES = 120


def set_working_memory(
    *,
    agent_id: str,
    thread_id: str,
    state: dict[str, Any],
    ttl_minutes: int = DEFAULT_TTL_MINUTES,
) -> dict[str, Any]:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=max(1, int(ttl_minutes))
    )
    with db_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO working_memory (agent_id, thread_id, state, updated_at, expires_at)
            VALUES (%s, %s, %s::jsonb, NOW(), %s)
            ON CONFLICT (agent_id, thread_id)
            DO UPDATE SET
                state = EXCLUDED.state,
                updated_at = NOW(),
                expires_at = EXCLUDED.expires_at
            RETURNING *
            """,
            (
                agent_id.strip(),
                thread_id.strip(),
                json.dumps(state, ensure_ascii=False),
                expires_at,
            ),
        ).fetchone()
        connection.commit()
    return row


def clear_working_memory(*, agent_id: str, thread_id: str) -> bool:
    with db_connection() as connection:
        result = connection.execute(
            """
            DELETE FROM working_memory
            WHERE agent_id = %s AND thread_id = %s
            """,
            (agent_id.strip(), thread_id.strip()),
        )
        connection.commit()
        return result.rowcount > 0


def list_working_memory() -> list[dict[str, Any]]:
    with db_connection() as connection:
        connection.execute(
            "DELETE FROM working_memory WHERE expires_at IS NOT NULL AND expires_at <= NOW()"
        )
        rows = connection.execute(
            """
            SELECT agent_id, thread_id, state, updated_at, expires_at
            FROM working_memory
            ORDER BY updated_at DESC
            """
        ).fetchall()
        connection.commit()
    return rows
