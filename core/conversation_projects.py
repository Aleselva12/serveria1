from __future__ import annotations

import json
import uuid
from typing import Any

from core.database import db_connection


def list_projects() -> list[dict[str, Any]]:
    with db_connection() as connection:
        return connection.execute(
            """
            SELECT p.id, p.name, p.shared_context, p.created_at, p.updated_at,
                   p.metadata, COUNT(c.id)::int AS conversation_count
            FROM conversation_projects p
            LEFT JOIN conversations c ON c.project_id = p.id
            GROUP BY p.id
            ORDER BY p.updated_at DESC, p.name ASC
            """
        ).fetchall()


def create_project(name: str, shared_context: str = "") -> dict[str, Any]:
    project_id = uuid.uuid4()
    with db_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO conversation_projects (id, name, shared_context)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (project_id, name.strip(), shared_context.strip()),
        ).fetchone()
        connection.commit()
    return row


def update_project(
    project_id: str,
    *,
    name: str | None = None,
    shared_context: str | None = None,
) -> dict[str, Any]:
    pid = uuid.UUID(project_id)
    with db_connection() as connection:
        current = connection.execute(
            "SELECT * FROM conversation_projects WHERE id=%s", (pid,)
        ).fetchone()
        if not current:
            raise KeyError(project_id)
        row = connection.execute(
            """
            UPDATE conversation_projects
            SET name=%s, shared_context=%s, updated_at=NOW()
            WHERE id=%s
            RETURNING *
            """,
            (
                (name if name is not None else current["name"]).strip(),
                (shared_context if shared_context is not None else current["shared_context"]).strip(),
                pid,
            ),
        ).fetchone()
        connection.commit()
    return row


def delete_project(project_id: str) -> bool:
    with db_connection() as connection:
        result = connection.execute(
            "DELETE FROM conversation_projects WHERE id=%s",
            (uuid.UUID(project_id),),
        )
        connection.commit()
        return result.rowcount > 0


def project_context_for_conversation(conversation_id: str) -> str:
    with db_connection() as connection:
        row = connection.execute(
            """
            SELECT p.shared_context
            FROM conversations c
            JOIN conversation_projects p ON p.id = c.project_id
            WHERE c.id=%s
            """,
            (uuid.UUID(conversation_id),),
        ).fetchone()
    return (row["shared_context"] if row else "").strip()
