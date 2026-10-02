from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from core.database import db_connection
from core.permissions import ApprovalPolicy, get_permission_rule


class ApprovalConflict(RuntimeError):
    pass


def _public(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def request_approval(
    *,
    actor: str,
    action: str,
    payload: dict[str, Any] | None = None,
    reason: str = "",
    metadata: dict[str, Any] | None = None,
    ttl_minutes: int = 60,
) -> dict[str, Any]:
    rule = get_permission_rule(actor, action)
    if rule is None:
        raise PermissionError("Nessuna regola di permesso definita per questa azione.")
    if rule.policy is ApprovalPolicy.BLOCKED:
        raise PermissionError("Azione bloccata dalla policy corrente.")
    if rule.policy is ApprovalPolicy.AUTO:
        raise ValueError("Questa azione non richiede approvazione.")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=max(1, ttl_minutes))
    with db_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO approval_requests
                (id, actor, action, scope, payload, reason, expires_at, metadata)
            VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb)
            RETURNING *
            """,
            (
                uuid.uuid4(), actor.strip().lower(), action.strip().lower(),
                rule.scope, json.dumps(payload or {}, ensure_ascii=False),
                reason.strip()[:2000], expires_at,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        ).fetchone()
        connection.commit()
    return _public(row)


def list_approvals(status: str = "pending", limit: int = 100) -> list[dict[str, Any]]:
    allowed = {"pending", "approved", "rejected", "consumed", "expired", ""}
    if status not in allowed:
        raise ValueError("Stato approvazione non valido.")
    limit = max(1, min(int(limit), 500))
    with db_connection() as connection:
        connection.execute(
            """
            UPDATE approval_requests
            SET status='expired', resolved_at=NOW(), resolved_by='system'
            WHERE status='pending' AND expires_at IS NOT NULL AND expires_at <= NOW()
            """
        )
        clause = "WHERE status=%s" if status else ""
        params = [status, limit] if status else [limit]
        rows = connection.execute(
            f"SELECT * FROM approval_requests {clause} ORDER BY created_at DESC LIMIT %s",
            params,
        ).fetchall()
        connection.commit()
    return [_public(row) for row in rows]


def resolve_approval(approval_id: str, approve: bool, *, resolved_by: str = "owner") -> dict[str, Any]:
    with db_connection() as connection:
        row = connection.execute(
            "SELECT * FROM approval_requests WHERE id=%s FOR UPDATE",
            (uuid.UUID(approval_id),),
        ).fetchone()
        if not row:
            raise KeyError("Approvazione non trovata.")
        if row["status"] != "pending":
            raise ApprovalConflict("L'approvazione è già stata risolta.")
        if row["expires_at"] and row["expires_at"] <= datetime.now(timezone.utc):
            connection.execute(
                "UPDATE approval_requests SET status='expired',resolved_at=NOW(),resolved_by='system' WHERE id=%s",
                (row["id"],),
            )
            connection.commit()
            raise ApprovalConflict("L'approvazione è scaduta.")
        status = "approved" if approve else "rejected"
        row = connection.execute(
            """
            UPDATE approval_requests
            SET status=%s,resolved_at=NOW(),resolved_by=%s
            WHERE id=%s RETURNING *
            """,
            (status, resolved_by, row["id"]),
        ).fetchone()
        connection.commit()
    return _public(row)


def consume_approval(approval_id: str, *, actor: str, action: str) -> dict[str, Any]:
    """Consume an approved request exactly once immediately before the side effect."""
    with db_connection() as connection:
        row = connection.execute(
            "SELECT * FROM approval_requests WHERE id=%s FOR UPDATE",
            (uuid.UUID(approval_id),),
        ).fetchone()
        if not row:
            raise KeyError("Approvazione non trovata.")
        if row["actor"] != actor.strip().lower() or row["action"] != action.strip().lower():
            raise PermissionError("L'approvazione non appartiene a questa azione.")
        if row["status"] != "approved":
            raise ApprovalConflict("L'azione non dispone di un'approvazione utilizzabile.")
        row = connection.execute(
            """
            UPDATE approval_requests
            SET status='consumed',consumed_at=NOW()
            WHERE id=%s RETURNING *
            """,
            (row["id"],),
        ).fetchone()
        connection.commit()
    return _public(row)
