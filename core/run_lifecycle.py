from __future__ import annotations

import json
import uuid
from typing import Any

from core.database import db_connection


STATUSES = {
    "queued", "running", "waiting_approval",
    "completed", "failed", "cancelled", "timed_out",
}
TERMINAL = {"completed", "failed", "cancelled", "timed_out"}
TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"waiting_approval", "completed", "failed", "cancelled", "timed_out"},
    "waiting_approval": {"running", "cancelled", "failed", "timed_out"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
    "timed_out": set(),
}


class RunConflict(RuntimeError):
    pass


def create_run(
    *,
    thread_id: str,
    kind: str = "chat",
    target: str = "supervisor",
    parent_run_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    identifier = uuid.UUID(run_id) if run_id else uuid.uuid4()
    with db_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO runtime_runs
                (id,thread_id,kind,target,parent_run_id,status,metadata)
            VALUES (%s,%s,%s,%s,%s,'queued',%s::jsonb)
            RETURNING *
            """,
            (
                identifier, thread_id, kind, target,
                uuid.UUID(parent_run_id) if parent_run_id else None,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        ).fetchone()
        connection.commit()
    return row


def transition_run(
    run_id: str,
    status: str,
    *,
    error_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError("Stato run non valido.")
    with db_connection() as connection:
        current = connection.execute(
            "SELECT * FROM runtime_runs WHERE id=%s FOR UPDATE",
            (uuid.UUID(run_id),),
        ).fetchone()
        if not current:
            raise KeyError("Run non trovato.")
        if status != current["status"] and status not in TRANSITIONS[current["status"]]:
            raise RunConflict(f"Transizione {current['status']} → {status} non consentita.")
        row = connection.execute(
            """
            UPDATE runtime_runs
            SET status=%s,
                started_at=CASE WHEN %s='running' AND started_at IS NULL THEN NOW() ELSE started_at END,
                finished_at=CASE WHEN %s IN ('completed','failed','cancelled','timed_out') THEN NOW() ELSE finished_at END,
                error_type=COALESCE(%s,error_type),
                metadata=metadata || %s::jsonb
            WHERE id=%s
            RETURNING *
            """,
            (
                status, status, status, error_type,
                json.dumps(metadata or {}, ensure_ascii=False),
                current["id"],
            ),
        ).fetchone()
        connection.commit()
    return row


def request_cancel(run_id: str) -> dict[str, Any]:
    """
    Record cooperative cancellation.

    Running synchronous LLM calls cannot be forcibly interrupted safely yet;
    components must inspect cancel_requested at safe boundaries.
    """
    with db_connection() as connection:
        row = connection.execute(
            """
            UPDATE runtime_runs
            SET cancel_requested=TRUE
            WHERE id=%s AND status NOT IN ('completed','failed','cancelled','timed_out')
            RETURNING *
            """,
            (uuid.UUID(run_id),),
        ).fetchone()
        if not row:
            raise RunConflict("Run non cancellabile o inesistente.")
        connection.commit()
    return row


def get_run(run_id: str) -> dict[str, Any]:
    with db_connection() as connection:
        row = connection.execute(
            "SELECT * FROM runtime_runs WHERE id=%s",
            (uuid.UUID(run_id),),
        ).fetchone()
    if not row:
        raise KeyError("Run non trovato.")
    return row


def list_runs(limit: int = 100, status: str = "") -> list[dict[str, Any]]:
    if status and status not in STATUSES:
        raise ValueError("Stato run non valido.")
    limit = max(1, min(int(limit), 500))
    clause = "WHERE status=%s" if status else ""
    params = [status, limit] if status else [limit]
    with db_connection() as connection:
        return connection.execute(
            f"SELECT * FROM runtime_runs {clause} ORDER BY created_at DESC LIMIT %s",
            params,
        ).fetchall()
