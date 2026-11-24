"""In-app notifications: Home window and Notifiche page. Owner only."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from core.access import require_owner


def owner(request: Request):
    require_owner(request, "notifications")


router = APIRouter(prefix="/api/v1/notifications/inbox", tags=["notifications"],
                   dependencies=[Depends(owner)])


def _public(row):
    return {"id": str(row["id"]), "createdAt": row["created_at"].isoformat(), "source": row["source"],
            "kind": row["kind"], "severity": row["severity"], "title": row["title"], "body": row["body"],
            "url": row["url"], "ref": row["ref"], "commit": row["commit_sha"],
            "seenAt": row["dismissed_at"].isoformat() if row["dismissed_at"] else None}


def _database(function):
    try:
        return function()
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(503, "Notifiche non disponibili: verifica il database.") from error


@router.get("")
def inbox(include_seen: bool = False, limit: int = Query(50, ge=1, le=200)):
    def read():
        from core.infra.database import db_connection
        with db_connection() as conn:
            rows = conn.execute(f"""SELECT * FROM app_notifications
                WHERE created_at<=NOW() {'' if include_seen else 'AND dismissed_at IS NULL'}
                ORDER BY created_at DESC LIMIT %s""", (limit,)).fetchall()
            unseen = conn.execute("SELECT COUNT(*) AS n FROM app_notifications WHERE dismissed_at IS NULL AND created_at<=NOW()").fetchone()["n"]
        return {"items": [_public(row) for row in rows], "unseen": unseen}
    return _database(read)


@router.post("/{notification_id}/seen")
def mark_seen(notification_id: UUID):
    def write():
        from core.infra.database import db_connection
        with db_connection() as conn:
            row = conn.execute("""UPDATE app_notifications SET dismissed_at=COALESCE(dismissed_at, NOW())
                WHERE id=%s AND created_at<=NOW() RETURNING id""", (str(notification_id),)).fetchone()
        if not row:
            raise HTTPException(404, "Notifica non trovata.")
        return {"seen": True}
    return _database(write)


@router.post("/seen")
def mark_all_seen():
    def write():
        from core.infra.database import db_connection
        with db_connection() as conn:
            count = conn.execute("UPDATE app_notifications SET dismissed_at=NOW() WHERE dismissed_at IS NULL AND created_at<=NOW()").rowcount
        return {"seen": count}
    return _database(write)
