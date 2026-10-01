from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pgvector import Vector

from core.database import database_status, db_connection
from core.embeddings import EMBEDDING_MODEL, embed_text
from core.logging import log_event


ALLOWED_MEMORY_TYPES = {
    "fact",
    "preference",
    "person",
    "project",
    "decision",
    "note",
    "task_context",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _public_memory(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in row.items()
        if key != "embedding"
    }


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
    """Create or update one persistent memory in PostgreSQL + pgvector."""
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
    embedding, embedding_model = embed_text(normalized_content)
    dimensions = len(embedding) if embedding else None
    parsed_expiry = datetime.fromisoformat(expires_at) if expires_at else None
    memory_id = uuid.uuid4()

    with db_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO memories (
                id, memory_type, key, content, source, importance,
                expires_at, embedding, embedding_model,
                embedding_dimensions, metadata
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s::jsonb
            )
            ON CONFLICT (memory_type, key)
            DO UPDATE SET
                content = EXCLUDED.content,
                source = EXCLUDED.source,
                importance = EXCLUDED.importance,
                updated_at = NOW(),
                expires_at = EXCLUDED.expires_at,
                embedding = EXCLUDED.embedding,
                embedding_model = EXCLUDED.embedding_model,
                embedding_dimensions = EXCLUDED.embedding_dimensions,
                metadata = EXCLUDED.metadata
            RETURNING *,
                CASE WHEN created_at = updated_at THEN 'created' ELSE 'updated' END AS action
            """,
            (
                memory_id,
                normalized_type,
                normalized_key,
                normalized_content,
                source,
                importance,
                parsed_expiry,
                Vector(embedding) if embedding else None,
                embedding_model,
                dimensions,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        ).fetchone()
        connection.execute(
            """
            INSERT INTO memory_sources (
                id, memory_id, source_type, source_ref, metadata
            )
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (
                uuid.uuid4(),
                row["id"],
                source,
                (metadata or {}).get("source_ref"),
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
        connection.commit()

    result = _public_memory(row)
    log_event(
        "memory_write",
        component="memory_store",
        thread_id=thread_id,
        data={
            "memory_id": str(result["id"]),
            "memory_type": normalized_type,
            "action": result["action"],
            "embedding_model": embedding_model,
            "embedding_dimensions": dimensions,
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
    """Hybrid lexical + semantic search over persistent memories."""
    limit = max(1, min(int(limit), 100))
    normalized_query = query.strip()
    normalized_type = memory_type.strip().lower()

    if normalized_type and normalized_type not in ALLOWED_MEMORY_TYPES:
        raise ValueError(
            "memory_type non valido. Valori ammessi: "
            + ", ".join(sorted(ALLOWED_MEMORY_TYPES))
        )

    query_embedding, embedding_model = (
        embed_text(normalized_query) if normalized_query else (None, None)
    )
    dimensions = len(query_embedding) if query_embedding else None

    clauses = ["(expires_at IS NULL OR expires_at > NOW())"]
    params: list[Any] = []

    if normalized_type:
        clauses.append("memory_type = %s")
        params.append(normalized_type)

    lexical_pattern = f"%{normalized_query}%" if normalized_query else None
    if normalized_query and query_embedding:
        score_sql = """
            (
                CASE WHEN key ILIKE %s OR content ILIKE %s THEN 1.0 ELSE 0.0 END
                +
                CASE
                    WHEN embedding IS NOT NULL
                     AND embedding_model = %s
                     AND embedding_dimensions = %s
                    THEN GREATEST(0.0, 1.0 - (embedding <=> %s))
                    ELSE 0.0
                END
            )
        """
        score_params = [
            lexical_pattern,
            lexical_pattern,
            embedding_model,
            dimensions,
            Vector(query_embedding),
        ]
    elif normalized_query:
        score_sql = "CASE WHEN key ILIKE %s OR content ILIKE %s THEN 1.0 ELSE 0.0 END"
        score_params = [lexical_pattern, lexical_pattern]
    else:
        score_sql = "0.0"
        score_params = []

    sql = f"""
        SELECT *,
               {score_sql} AS search_score
        FROM memories
        WHERE {' AND '.join(clauses)}
        ORDER BY search_score DESC, importance DESC, updated_at DESC
        LIMIT %s
    """

    with db_connection() as connection:
        rows = connection.execute(
            sql,
            [*score_params, *params, limit],
        ).fetchall()

    results = [_public_memory(row) for row in rows]
    log_event(
        "memory_read",
        component="memory_store",
        thread_id=thread_id,
        data={
            "query_chars": len(normalized_query),
            "memory_type": normalized_type or None,
            "result_count": len(results),
            "semantic_search": bool(query_embedding),
            "embedding_model": embedding_model,
        },
    )
    return results


def delete_memory(memory_id: str, *, thread_id: str | None = None) -> bool:
    with db_connection() as connection:
        result = connection.execute(
            "DELETE FROM memories WHERE id = %s",
            (uuid.UUID(memory_id.strip()),),
        )
        deleted = result.rowcount > 0
        connection.commit()

    log_event(
        "memory_delete",
        component="memory_store",
        thread_id=thread_id,
        data={"memory_id": memory_id, "deleted": deleted},
    )
    return deleted


def memory_stats() -> dict[str, Any]:
    status = database_status()
    if not status.get("reachable"):
        return {
            "backend": "postgresql+pgvector",
            "available": False,
            "total": 0,
            "by_type": {},
            "embedding_model": EMBEDDING_MODEL,
            "database": status,
        }

    with db_connection() as connection:
        total = connection.execute(
            "SELECT COUNT(*) AS count FROM memories"
        ).fetchone()["count"]
        embedded = connection.execute(
            "SELECT COUNT(*) AS count FROM memories WHERE embedding IS NOT NULL"
        ).fetchone()["count"]
        by_type_rows = connection.execute(
            "SELECT memory_type, COUNT(*) AS count FROM memories GROUP BY memory_type"
        ).fetchall()

    return {
        "backend": "postgresql+pgvector",
        "available": True,
        "total": int(total),
        "embedded": int(embedded),
        "by_type": {row["memory_type"]: int(row["count"]) for row in by_type_rows},
        "embedding_model": EMBEDDING_MODEL,
        "database": status,
    }
