"""Owner-facing push subscriptions and calendar reminder worker."""
from __future__ import annotations

import json
import threading
from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg import OperationalError

from core.access import require_owner
from core.database import db_connection
from core import webpush


def owner(request: Request):
    require_owner(request, "notifications")


router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["notifications"],
    dependencies=[Depends(owner)],
)


class SubscriptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(min_length=20, max_length=4096)
    p256dh: str = Field(min_length=20, max_length=512)
    auth: str = Field(min_length=8, max_length=256)
    label: str = Field(default="iPhone", min_length=1, max_length=80)
    user_agent: str = Field(default="", max_length=500)

    @field_validator("endpoint")
    @classmethod
    def https_endpoint(cls, value: str):
        if not value.startswith("https://"):
            raise ValueError("L'endpoint push deve usare HTTPS.")
        return value


class EndpointInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(min_length=20, max_length=4096)


def _safe(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except (OperationalError, RuntimeError) as error:
        raise HTTPException(503, "Notifiche non disponibili.") from error


def _subscription(endpoint: str):
    with db_connection() as conn:
        return conn.execute(
            "SELECT * FROM push_subscriptions WHERE endpoint=%s", (endpoint,)
        ).fetchone()


@router.get("/config")
def config():
    try:
        return {"supported": True, "publicKey": webpush.public_key()}
    except (OSError, ValueError, RuntimeError):
        return {"supported": False, "publicKey": None}


@router.get("/status")
def status():
    def load():
        with db_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM push_subscriptions WHERE active"
            ).fetchone()
        return {"activeSubscriptions": row["count"]}
    return _safe(load)


@router.post("/subscriptions", status_code=201)
def subscribe(data: SubscriptionInput):
    def save():
        with db_connection() as conn:
            row = conn.execute(
                """INSERT INTO push_subscriptions
                (id,endpoint,p256dh,auth,label,user_agent,active)
                VALUES (%s,%s,%s,%s,%s,%s,TRUE)
                ON CONFLICT(endpoint) DO UPDATE SET
                  p256dh=EXCLUDED.p256dh,auth=EXCLUDED.auth,label=EXCLUDED.label,
                  user_agent=EXCLUDED.user_agent,active=TRUE,updated_at=NOW(),last_error=NULL
                RETURNING id,label,active,created_at,updated_at""",
                (uuid4(), data.endpoint, data.p256dh, data.auth, data.label, data.user_agent),
            ).fetchone()
            conn.commit()
        return {**row, "id": str(row["id"])}
    return _safe(save)


@router.delete("/subscriptions")
def unsubscribe(data: EndpointInput):
    def remove():
        with db_connection() as conn:
            result = conn.execute(
                "UPDATE push_subscriptions SET active=FALSE,updated_at=NOW() WHERE endpoint=%s",
                (data.endpoint,),
            )
            conn.commit()
        return {"disabled": bool(result.rowcount)}
    return _safe(remove)


def _mark_result(subscription_id, *, error: str | None = None):
    with db_connection() as conn:
        if error:
            conn.execute(
                """UPDATE push_subscriptions SET last_attempt_at=NOW(),
                   last_error=%s,updated_at=NOW() WHERE id=%s""",
                (error[:500], subscription_id),
            )
        else:
            conn.execute(
                """UPDATE push_subscriptions SET last_attempt_at=NOW(),last_success_at=NOW(),
                   last_error=NULL,updated_at=NOW() WHERE id=%s""",
                (subscription_id,),
            )
        conn.commit()


def _disable(subscription_id, error: str):
    with db_connection() as conn:
        conn.execute(
            """UPDATE push_subscriptions SET active=FALSE,last_attempt_at=NOW(),
               last_error=%s,updated_at=NOW() WHERE id=%s""",
            (error[:500], subscription_id),
        )
        conn.commit()


def send_one(row, payload: dict, *, ttl=300) -> bool:
    try:
        webpush.send(row["endpoint"], row["p256dh"], row["auth"], payload, ttl=ttl)
        _mark_result(row["id"])
        return True
    except webpush.PushGone as error:
        _disable(row["id"], str(error))
        return False
    except Exception as error:
        _mark_result(row["id"], error=type(error).__name__ + ": " + str(error))
        return False


@router.post("/test")
def test_push(data: EndpointInput):
    row = _safe(_subscription, data.endpoint)
    if not row or not row["active"]:
        raise HTTPException(404, "Questo dispositivo non risulta registrato.")
    payload = {
        "title": "Cora · Notifica di prova",
        "body": "Le notifiche push funzionano correttamente.",
        "url": "/#calendar",
        "tag": "cora-test",
    }
    if not send_one(row, payload):
        raise HTTPException(502, "Invio push non riuscito. Controlla HTTPS e la registrazione del dispositivo.")
    return {"sent": True}


def _due_events():
    with db_connection() as conn:
        return conn.execute(
            """SELECT * FROM calendar_events
               WHERE deleted_at IS NULL
                 AND all_day=FALSE
                 AND reminder_minutes IS NOT NULL
                 AND start_at > NOW()
                 AND start_at - make_interval(mins => reminder_minutes) <= NOW()
               ORDER BY start_at
               LIMIT 100"""
        ).fetchall()


def _active_subscriptions():
    with db_connection() as conn:
        return conn.execute(
            "SELECT * FROM push_subscriptions WHERE active ORDER BY created_at"
        ).fetchall()


def _already_delivered(subscription_id, event) -> bool:
    with db_connection() as conn:
        row = conn.execute(
            """SELECT 1 FROM notification_deliveries
               WHERE subscription_id=%s AND event_id=%s AND event_version=%s AND kind='calendar_reminder'""",
            (subscription_id, event["id"], event["version"]),
        ).fetchone()
    return bool(row)


def _record_delivery(subscription_id, event):
    scheduled = event["start_at"] - __import__("datetime").timedelta(minutes=event["reminder_minutes"])
    with db_connection() as conn:
        conn.execute(
            """INSERT INTO notification_deliveries
               (id,subscription_id,event_id,event_version,kind,scheduled_for)
               VALUES (%s,%s,%s,%s,'calendar_reminder',%s)
               ON CONFLICT(subscription_id,event_id,event_version,kind) DO NOTHING""",
            (uuid4(), subscription_id, event["id"], event["version"], scheduled),
        )
        conn.commit()


def _calendar_payload(event) -> dict:
    local = event["start_at"].astimezone(ZoneInfo("Europe/Rome"))
    minutes = event["reminder_minutes"]
    when = local.strftime("%H:%M")
    lead = f"Tra {minutes} minuti" if minutes < 60 else (
        "Tra 1 ora" if minutes == 60 else
        f"Tra {minutes // 60} ore" if minutes < 1440 and minutes % 60 == 0 else
        "Domani" if minutes == 1440 else f"Promemoria · {when}"
    )
    return {
        "title": "Cora · Calendario",
        "body": f"{lead}: {event['title']} · {when}",
        "url": "/#calendar",
        "tag": f"calendar-{event['id']}-{event['version']}",
    }


def deliver_calendar_reminders():
    events = _due_events()
    if not events:
        return
    subscriptions = _active_subscriptions()
    for event in events:
        payload = _calendar_payload(event)
        for subscription in subscriptions:
            if _already_delivered(subscription["id"], event):
                continue
            if send_one(subscription, payload, ttl=max(300, min(86400, event["reminder_minutes"] * 60))):
                _record_delivery(subscription["id"], event)


class NotificationWorker:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="cora-notifications", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        while not self._stop.wait(20):
            try:
                deliver_calendar_reminders()
            except Exception:
                # Push is best-effort and must never take down Cora.
                pass


worker = NotificationWorker()
