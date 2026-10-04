from __future__ import annotations

import json
import os
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


class MemoryConflict(ValueError):
    """The caller has not read the current version. No memory was changed."""


ASSERTIONS = {"user_statement", "observation", "inference", "unclassified"}


def _owner_update_approved(action="remember_memory"):
    from core.governance import invocation, approved_action
    call, grant = invocation.get(), approved_action.get()
    return bool(call and grant and grant[0] == call["actor"]
                and action in grant[1] and grant[2:] == (call["tool_id"], call["payload"]))


def save_memory(
    *, memory_type: str, key: str, content: str, source: str = "user_explicit",
    importance: int = 3, expires_at: str | None = None,
    metadata: dict[str, Any] | None = None, thread_id: str | None = None,
    assertion: str = "user_statement", confidence: float | None = None,
    expected_version: int = 0, editor: str = "user", source_ref: str | None = None,
    expected_memory_id: str | None = None,
) -> dict[str, Any]:
    """Versioned write. expected_version=0 creates; updates require a read version.

    editor is supplied by trusted entrypoints, never model arguments or metadata.
    Agent updates of owner/legacy memories require an exact-action owner approval.
    """
    normalized_type, normalized_key, normalized_content = memory_type.strip().lower(), key.strip(), content.strip()
    if normalized_type not in ALLOWED_MEMORY_TYPES:
        raise ValueError("memory_type non valido.")
    if not normalized_key or len(normalized_key) > 200 or not normalized_content or len(normalized_content) > 12000:
        raise ValueError("Chiave (1–200 caratteri) e contenuto (1–12000) richiesti.")
    if assertion not in ASSERTIONS or editor not in {"user", "agent"}:
        raise ValueError("Classificazione o autore non valido.")
    if confidence is not None and not 0 <= confidence <= 1:
        raise ValueError("La confidenza deve essere tra 0 e 1.")
    if editor == "agent" and assertion == "unclassified":
        raise ValueError("L'agente deve distinguere affermazioni, osservazioni e deduzioni.")
    if expected_version < 0 or not 1 <= importance <= 5:
        raise ValueError("Versione o importanza non valida.")
    parsed_expiry = datetime.fromisoformat(expires_at) if expires_at else None
    if parsed_expiry and (parsed_expiry.tzinfo is None or parsed_expiry <= _utc_now()):
        raise ValueError("La scadenza deve essere futura e includere il fuso orario.")
    from psycopg.types.json import Jsonb
    # Serialize competing creates as well as edits, without holding a lock during embeddings.
    # The text commits immediately; derived embeddings are indexed in the idle worker.
    with db_connection() as connection:
        connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (normalized_type + ":" + normalized_key,))
        previous = connection.execute("SELECT * FROM memories WHERE memory_type=%s AND key=%s FOR UPDATE",
                                      (normalized_type, normalized_key)).fetchone()
        if (previous["version"] if previous else 0) != expected_version:
            raise MemoryConflict("Memoria cambiata: rileggi la versione corrente prima di aggiornare.")
        if previous and (not expected_memory_id or str(previous['id']) != str(uuid.UUID(expected_memory_id))):
            raise MemoryConflict("Identità della memoria cambiata: rileggi ID e versione prima di aggiornare.")
        if not previous and expected_memory_id:
            raise MemoryConflict("La memoria letta è stata eliminata; la creazione richiede una nuova richiesta.")
        if previous and editor == "agent" and previous["owner_kind"] != "agent" and not _owner_update_approved():
            from core.governance import ApprovalRequired
            raise ApprovalRequired("supervisor", "remember_memory")
        owner = previous["owner_kind"] if previous else editor
        if editor == "user": owner = "user"
        data = dict(metadata or {})
        # These references cannot be overridden by metadata from the model.
        data.update(editor=editor, source_ref=source_ref, thread_id=thread_id)
        row = connection.execute("""
            INSERT INTO memories (id,memory_type,key,content,source,importance,expires_at,
                metadata,assertion,confidence,owner_kind,version)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
            ON CONFLICT (memory_type,key) DO UPDATE SET
                content=EXCLUDED.content,source=EXCLUDED.source,importance=EXCLUDED.importance,
                expires_at=EXCLUDED.expires_at,metadata=EXCLUDED.metadata,assertion=EXCLUDED.assertion,
                confidence=EXCLUDED.confidence,owner_kind=EXCLUDED.owner_kind,
                version=memories.version+1,updated_at=NOW(),embedding=NULL,
                embedding_model=NULL,embedding_dimensions=NULL
            RETURNING *""", (uuid.uuid4(),normalized_type,normalized_key,normalized_content,source,
                importance,parsed_expiry,Jsonb(data),assertion,confidence,owner)).fetchone()
        connection.execute("""INSERT INTO memory_versions (memory_id,version,snapshot,editor)
            SELECT id,version,to_jsonb(memories)-'embedding',%s FROM memories WHERE id=%s""", (editor,row["id"]))
        connection.execute("""INSERT INTO memory_sources (id,memory_id,source_type,source_ref,metadata)
            VALUES (%s,%s,%s,%s,%s)""", (uuid.uuid4(),row["id"],source,source_ref,Jsonb({**data,"version":row["version"]})))
    result = _public_memory(row)
    result["action"] = "updated" if previous else "created"
    log_event("memory_write", component="memory_store", thread_id=thread_id,
              data={"memory_id":str(row["id"]),"version":row["version"],"assertion":assertion,"action":result["action"]})
    return result


def memory_history(memory_id: str, *, limit: int = 50):
    with db_connection() as connection:
        return connection.execute("""SELECT version,snapshot,editor,created_at FROM memory_versions
            WHERE memory_id=%s ORDER BY version DESC LIMIT %s""", (uuid.UUID(memory_id),max(1,min(limit,100)))).fetchall()


def search_memories(
    query: str = "",
    *,
    memory_type: str = "",
    limit: int = 20,
    thread_id: str | None = None,
    include_expired: bool = False,
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

    # Do not load an embedding model for an empty memory store.
    with db_connection() as connection:
        if not connection.execute("SELECT EXISTS(SELECT 1 FROM memories WHERE %s OR expires_at IS NULL OR expires_at > NOW()) AS present",(include_expired,)).fetchone()["present"]:
            return []
    query_embedding, embedding_model = (
        embed_text(normalized_query, timeout=float(os.getenv("CORA_MEMORY_EMBED_TIMEOUT_SECONDS", "5")), cached=True)
        if normalized_query else (None, None)
    )
    dimensions = len(query_embedding) if query_embedding else None

    clauses = ["(%s OR expires_at IS NULL OR expires_at > NOW())"]
    params: list[Any] = [include_expired]

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

    minimum = float(os.getenv("CORA_MEMORY_MIN_SCORE", "0.25")) if query_embedding else 0.0
    sql = f"""
        SELECT * FROM (
        SELECT *,
               {score_sql} AS search_score
        FROM memories
        WHERE {' AND '.join(clauses)}
        ) ranked
        WHERE search_score > %s OR %s
        ORDER BY search_score DESC, importance DESC, updated_at DESC
        LIMIT %s
    """

    with db_connection() as connection:
        rows = connection.execute(
            sql,
            [*score_params, *params, minimum, not normalized_query, limit],
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


def delete_memory(memory_id: str, *, thread_id: str | None = None, editor="user", expected_version=None) -> bool:
    with db_connection() as connection:
        row = connection.execute("SELECT * FROM memories WHERE id=%s FOR UPDATE",(uuid.UUID(memory_id),)).fetchone()
        if row and editor == 'agent':
            if expected_version != row['version']: raise MemoryConflict("Rileggi la versione prima di eliminare.")
            if row['owner_kind'] != 'agent' and not _owner_update_approved('forget_memory'):
                from core.governance import ApprovalRequired
                raise ApprovalRequired('supervisor','forget_memory')
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
