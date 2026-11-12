from __future__ import annotations

import json
import uuid
from typing import Any

from core.database import db_connection
from core.logging import log_event


def create_episode(
    *,
    title: str,
    summary: str,
    conversation_id: str | None = None,
    episode_type: str = "conversation",
    agent_id: str | None = None,
    importance: int = 3,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_title = title.strip()[:160] or "Episodio"
    normalized_summary = summary.strip()
    if not normalized_summary:
        raise ValueError("summary non può essere vuoto")
    importance = max(1, min(int(importance), 5))

    with db_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO episodes (
                id, conversation_id, title, summary, episode_type,
                agent_id, importance, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING *
            """,
            (
                uuid.uuid4(),
                uuid.UUID(conversation_id) if conversation_id else None,
                normalized_title,
                normalized_summary,
                episode_type.strip() or "conversation",
                agent_id,
                importance,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        ).fetchone()
        connection.commit()

    log_event(
        "episode_write",
        component="episodic_memory",
        thread_id=conversation_id,
        data={"episode_id": str(row["id"]), "episode_type": row["episode_type"]},
    )
    return row


def list_episodes(*, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    with db_connection() as connection:
        return connection.execute(
            """
            SELECT *
            FROM episodes
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
