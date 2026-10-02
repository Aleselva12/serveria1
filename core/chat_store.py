from __future__ import annotations

import json
import os
import uuid
from typing import Any

from pgvector import Vector

from core.database import db_connection
from core.embeddings import embed_text
from core.transcripts import write_transcript


CHAT_CONTEXT_MESSAGES = max(2, int(os.getenv("CORA_CHAT_CONTEXT_MESSAGES", "40")))


def ensure_conversation(
    conversation_id: str,
    *,
    title: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cid = uuid.UUID(conversation_id)
    with db_connection() as connection:
        row = connection.execute(
            "SELECT * FROM conversations WHERE id = %s",
            (cid,),
        ).fetchone()
        if row:
            return row

        normalized_title = (title or "Nuova chat").strip()[:160] or "Nuova chat"
        row = connection.execute(
            """
            INSERT INTO conversations (id, title, metadata)
            VALUES (%s, %s, %s::jsonb)
            RETURNING *
            """,
            (cid, normalized_title, json.dumps(metadata or {}, ensure_ascii=False)),
        ).fetchone()
        connection.commit()
        return row


def _auto_title(content: str) -> str:
    single_line = " ".join(content.split())
    return single_line[:80] or "Nuova chat"


def save_message(
    *,
    conversation_id: str,
    role: str,
    content: str,
    agent_id: str | None = None,
    model_id: str | None = None,
    parent_message_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    refresh_transcript_now: bool = True,
) -> dict[str, Any]:
    if role not in {"user", "assistant", "system"}:
        raise ValueError("role non valido")
    normalized = content.strip()
    if not normalized:
        raise ValueError("content non può essere vuoto")

    conversation = ensure_conversation(conversation_id)
    embedding, embedding_model = None, None  # Indexed later by the idle background worker.
    embedding_dimensions = len(embedding) if embedding else None
    message_id = uuid.uuid4()

    with db_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO messages (
                id, conversation_id, role, content, agent_id, model_id,
                parent_message_id, embedding, embedding_model,
                embedding_dimensions, metadata
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s::jsonb
            )
            RETURNING *
            """,
            (
                message_id,
                uuid.UUID(conversation_id),
                role,
                normalized,
                agent_id,
                model_id,
                uuid.UUID(parent_message_id) if parent_message_id else None,
                Vector(embedding) if embedding else None,
                embedding_model,
                embedding_dimensions,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        ).fetchone()

        title = conversation["title"]
        if role == "user" and title == "Nuova chat":
            title = _auto_title(normalized)
        connection.execute(
            """
            UPDATE conversations
            SET title = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (title, uuid.UUID(conversation_id)),
        )
        connection.commit()

    if refresh_transcript_now:
        refresh_transcript(conversation_id)
    return row


def list_conversations(*, limit: int = 100, include_archived: bool = False) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    archived_clause = "" if include_archived else "WHERE archived = FALSE"
    with db_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT id, title, created_at, updated_at, archived, transcript_path, metadata
            FROM conversations
            {archived_clause}
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return rows


def get_messages(conversation_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    params: list[Any] = [uuid.UUID(conversation_id)]
    sql = """
        SELECT
            id, conversation_id, role, content, created_at,
            agent_id, model_id, parent_message_id, metadata
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at ASC, id ASC
    """
    if limit is not None:
        safe_limit = max(1, min(int(limit), 2000))
        sql = """
            SELECT * FROM (
                SELECT
                    id, conversation_id, role, content, created_at,
                    agent_id, model_id, parent_message_id, metadata
                FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
            ) recent
            ORDER BY created_at ASC, id ASC
        """
        params.append(safe_limit)

    with db_connection() as connection:
        return connection.execute(sql, params).fetchall()


def recent_context(conversation_id: str) -> list[dict[str, str]]:
    rows = get_messages(conversation_id, limit=CHAT_CONTEXT_MESSAGES)
    return [
        {"role": row["role"], "content": row["content"]}
        for row in rows
        if row["role"] in {"user", "assistant", "system"}
    ]


def refresh_transcript(conversation_id: str) -> str:
    with db_connection() as connection:
        conversation = connection.execute(
            "SELECT * FROM conversations WHERE id = %s",
            (uuid.UUID(conversation_id),),
        ).fetchone()
        if not conversation:
            raise KeyError(conversation_id)
        messages = connection.execute(
            """
            SELECT id, role, content, created_at, agent_id, model_id, metadata
            FROM messages
            WHERE conversation_id = %s
            ORDER BY created_at ASC, id ASC
            """,
            (uuid.UUID(conversation_id),),
        ).fetchall()

    path = write_transcript(conversation, messages)
    with db_connection() as connection:
        connection.execute(
            "UPDATE conversations SET transcript_path = %s WHERE id = %s",
            (str(path), uuid.UUID(conversation_id)),
        )
        connection.commit()
    return str(path)


def conversation_stats() -> dict[str, int]:
    with db_connection() as connection:
        row = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM conversations) AS conversations,
                (SELECT COUNT(*) FROM messages) AS messages
            """
        ).fetchone()
    return {
        "conversations": int(row["conversations"]),
        "messages": int(row["messages"]),
    }
