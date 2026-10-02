"""Authoritative calendar store. All writes and their history share one transaction."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from psycopg.types.json import Jsonb

from core.database import db_connection
from core.permissions import check_permission, require_permission


class CalendarConflict(ValueError):
    pass


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    start: datetime
    end: datetime
    all_day: bool = False
    notes: str = Field(default="", max_length=10000)

    @model_validator(mode="after")
    def validate_event(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("Inserisci un titolo.")
        for value in (self.start, self.end):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Data e ora devono includere il fuso orario.")
        if self.end <= self.start:
            raise ValueError("La fine deve essere successiva all'inizio.")
        if self.all_day:
            from zoneinfo import ZoneInfo
            for value in (self.start, self.end):
                local = value.astimezone(ZoneInfo("Europe/Rome"))
                if any((local.hour, local.minute, local.second, local.microsecond)):
                    raise ValueError("Gli eventi tutto il giorno iniziano e terminano a mezzanotte italiana (fine esclusa).")
        return self


def json_row(row):
    if row is None:
        return None
    return {key: value.isoformat() if isinstance(value, datetime) else str(value) if isinstance(value, UUID) else value
            for key, value in row.items()}


def _audit(conn, row, action, actor):
    conn.execute("""INSERT INTO calendar_event_history (id,event_id,action,actor,snapshot)
                    VALUES (%s,%s,%s,%s,%s)""",
                 (uuid4(), row["id"], action, actor, Jsonb(json_row(row))))


def list_events(start: datetime, end: datetime, *, deleted=False):
    if start.tzinfo is None or end.tzinfo is None or end <= start:
        raise ValueError("Intervallo non valido: specifica inizio, fine e fuso orario.")
    if end - start > timedelta(days=370):
        raise ValueError("Consulta al massimo 370 giorni per richiesta.")
    with db_connection() as conn:
        rows = conn.execute("""SELECT * FROM calendar_events WHERE
                            (deleted_at IS NOT NULL) = %s AND start_at < %s AND end_at > %s
                            ORDER BY start_at, id""", (deleted, end, start)).fetchall()
    return [serialize_event(r) for r in rows]


def serialize_event(row):
    result = json_row(row)
    result["start"] = result.pop("start_at")
    result["end"] = result.pop("end_at")
    return result


def get_event(event_id: str, *, include_deleted=False, conn=None):
    if conn is None:
        with db_connection() as connection:
            return get_event(event_id, include_deleted=include_deleted, conn=connection)
    row = conn.execute("SELECT * FROM calendar_events WHERE id=%s", (UUID(event_id),)).fetchone()
    if not row or (row["deleted_at"] and not include_deleted):
        raise KeyError("Evento non trovato.")
    return serialize_event(row)


def _write(conn, action: str, *, actor: str, event_id=None, version=None, data=None):
    if action == "create":
        data = EventInput.model_validate(data)
        row = conn.execute("""INSERT INTO calendar_events
            (id,title,start_at,end_at,all_day,notes,created_by,updated_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (uuid4(), data.title, data.start, data.end, data.all_day, data.notes, actor, actor)).fetchone()
    else:
        if action not in {"update", "delete", "restore"}:
            raise ValueError("Azione non valida.")
        row = conn.execute("SELECT * FROM calendar_events WHERE id=%s FOR UPDATE", (UUID(event_id),)).fetchone()
        if not row:
            raise KeyError("Evento non trovato.")
        if row["version"] != version:
            raise CalendarConflict("L'evento è cambiato. Riapri l'evento prima di modificare o approvare.")
        if (action == "restore") != bool(row["deleted_at"]):
            raise CalendarConflict("Lo stato dell'evento è cambiato. Ricarica il calendario.")
        if action == "update":
            data = EventInput.model_validate(data)
            row = conn.execute("""UPDATE calendar_events SET title=%s,start_at=%s,end_at=%s,
                all_day=%s,notes=%s,updated_by=%s,updated_at=NOW(),version=version+1
                WHERE id=%s RETURNING *""",
                (data.title, data.start, data.end, data.all_day, data.notes, actor, row["id"])).fetchone()
        else:
            deleted_at = datetime.now(timezone.utc) if action == "delete" else None
            row = conn.execute("""UPDATE calendar_events SET deleted_at=%s,updated_by=%s,
                updated_at=NOW(),version=version+1 WHERE id=%s RETURNING *""",
                (deleted_at, actor, row["id"])).fetchone()
    _audit(conn, row, action, actor)
    return serialize_event(row)


def write_event(action, *, actor="user", event_id=None, version=None, data=None):
    # Non-user actors can write only through a persisted owner-approved proposal.
    if actor != "user":
        raise PermissionError("Gli agenti devono utilizzare una proposta calendario.")
    with db_connection() as conn:
        result = _write(conn, action, actor=actor, event_id=event_id, version=version, data=data)
        conn.commit()
        return result


def event_history(event_id):
    with db_connection() as conn:
        get_event(event_id, include_deleted=True, conn=conn)
        return [json_row(r) for r in conn.execute(
            "SELECT * FROM calendar_event_history WHERE event_id=%s ORDER BY changed_at DESC, id",
            (UUID(event_id),)).fetchall()]


def propose_event(actor, action, *, event_id=None, version=None, data=None, reason=""):
    decision = check_permission(actor, "calendar_" + action + "_event")
    if not decision.rule or decision.rule.policy.value == "blocked":
        raise PermissionError(decision.reason)
    if action not in {"create", "update", "delete"}:
        raise ValueError("Azione non valida.")
    normalized = EventInput.model_validate(data).model_dump(mode="json") if action != "delete" else {}
    with db_connection() as conn:
        previous = {}
        if action != "create":
            current = get_event(event_id, conn=conn)
            previous = current
            if current["version"] != version:
                raise CalendarConflict("L'evento è cambiato. Rileggilo prima di proporre una modifica.")
        row = conn.execute("""INSERT INTO calendar_proposals
            (id,actor,action,event_id,expected_version,payload,previous,reason) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (uuid4(), actor, action, UUID(event_id) if event_id else None, version, Jsonb(normalized), Jsonb(previous), reason[:2000])).fetchone()
        conn.commit()
        return {"status": "pending", "proposal": json_row(row),
                "message": "Proposta salvata: richiede approvazione dalla pagina Calendario. L'evento non è ancora stato modificato."}


def list_proposals():
    with db_connection() as conn:
        return [json_row(r) for r in conn.execute(
            "SELECT * FROM calendar_proposals WHERE status='pending' ORDER BY created_at").fetchall()]


def resolve_proposal(proposal_id, approve: bool):
    with db_connection() as conn:
        row = conn.execute("SELECT * FROM calendar_proposals WHERE id=%s FOR UPDATE", (UUID(proposal_id),)).fetchone()
        if not row:
            raise KeyError("Proposta non trovata.")
        if row["status"] != "pending":
            raise CalendarConflict("La proposta è già stata gestita.")
        event = None
        if approve:
            require_permission(row["actor"], "calendar_" + row["action"] + "_event", user_approved=True)
            event = _write(conn, row["action"], actor=row["actor"], event_id=str(row["event_id"]),
                           version=row["expected_version"], data=row["payload"])
        result = conn.execute("""UPDATE calendar_proposals SET status=%s,resolved_at=NOW(),resolved_by='user'
                                 WHERE id=%s RETURNING *""",
                              ("approved" if approve else "rejected", row["id"])).fetchone()
        conn.commit()
        return {"proposal": json_row(result), "event": event}
