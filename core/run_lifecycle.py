from __future__ import annotations

import json
import threading
import uuid
from typing import Any

from core.database import db_connection


from core.runtime import TRANSITIONS as RUNTIME_TRANSITIONS, TERMINAL as RUNTIME_TERMINAL

TERMINAL = set(RUNTIME_TERMINAL)
TRANSITIONS = {key: set(value) for key,value in RUNTIME_TRANSITIONS.items()}
for status in TERMINAL: TRANSITIONS[status] = set()
# Compatibility for old persisted rows; owner approvals no longer resume a run.
TRANSITIONS["running"].add("waiting_approval")
TRANSITIONS["waiting_approval"] = {"running", "cancelled", "failed", "timed_out", "interrupted"}
STATUSES = set(TRANSITIONS)



class RunConflict(RuntimeError):
    pass


class RunCancelled(RuntimeError):
    pass


_cancelled: set[str] = set()
_cancel_lock = threading.Lock()


def cancel_requested(run_id: str) -> bool:
    with _cancel_lock:
        return run_id in _cancelled


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
                finished_at=CASE WHEN %s IN ('completed','failed','cancelled','timed_out','awaiting_approval','interrupted') THEN NOW() ELSE finished_at END,
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
    if status in TERMINAL:
        with _cancel_lock:
            _cancelled.discard(str(run_id))
    return row


def request_cancel(run_id: str) -> dict[str, Any]:
    """
    Record cooperative cancellation.

    Running synchronous LLM calls cannot be forcibly interrupted safely yet;
    components must inspect cancel_requested at safe boundaries.
    """
    from core.runtime import runtime
    live = runtime.get(run_id)
    if live:
        live.stop()
        return get_run(run_id)
    with db_connection() as connection:
        row = connection.execute(
            """
            UPDATE runtime_runs
            SET cancel_requested=TRUE
            WHERE id=%s AND status NOT IN ('completed','failed','cancelled','timed_out','awaiting_approval','interrupted')
            RETURNING *
            """,
            (uuid.UUID(run_id),),
        ).fetchone()
        if not row:
            raise RunConflict("Run non cancellabile o inesistente.")
        connection.commit()
    with _cancel_lock:
        _cancelled.add(str(run_id))
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



def persist_live_run(run):
    from core.database import database_configured
    if not database_configured(): return
    with db_connection() as conn:
        conn.execute("""INSERT INTO runtime_runs (id,thread_id,status,started_at,finished_at,cancel_requested,error_type,metadata)
            VALUES (%s,%s,%s,CASE WHEN %s THEN NOW() END,CASE WHEN %s THEN NOW() END,%s,%s,%s::jsonb)
            ON CONFLICT(id) DO UPDATE SET status=EXCLUDED.status,
            started_at=COALESCE(runtime_runs.started_at,EXCLUDED.started_at), finished_at=EXCLUDED.finished_at,
            cancel_requested=EXCLUDED.cancel_requested,error_type=EXCLUDED.error_type,metadata=EXCLUDED.metadata""",
            (uuid.UUID(run.id),run.thread_id,run.status,run.started is not None,run.status in TERMINAL,
             run.cancel.is_set(),run.error_type,json.dumps({"graph_version":run.graph_version,"metrics":run.timings},default=str)))
