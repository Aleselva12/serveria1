from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from psycopg import OperationalError
from googleapiclient.errors import HttpError

from core import calendar as store
from core import google_calendar
from core.access import require_owner


def calendar_owner(request: Request):
    require_owner(request, "calendar")


router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"], dependencies=[Depends(calendar_owner)])


class EventUpdate(store.EventInput):
    version: int = Field(ge=1)


class Decision(BaseModel):
    approve: bool


def run(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except store.CalendarConflict as error:
        raise HTTPException(409, str(error)) from error
    except KeyError as error:
        raise HTTPException(404, str(error)) from error
    except PermissionError as error:
        raise HTTPException(403, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except google_calendar.GoogleCalendarNotConnected as error:
        raise HTTPException(503, str(error)) from error
    except HttpError as error:
        raise HTTPException(502, "Google Calendar non disponibile o autorizzazione insufficiente.") from error
    except (OperationalError, RuntimeError) as error:
        raise HTTPException(503, "Calendario non disponibile: verifica PostgreSQL/Google Calendar.") from error


@router.get("/provider")
def provider():
    return google_calendar.status()


@router.post("/sync/google")
def sync_google():
    if not google_calendar.token_exists():
        raise HTTPException(
            503,
            "Google Calendar non è ancora collegato al server. Autorizza prima l'account Google e poi riprova.",
        )
    local_events = run(store.list_future_events)
    return run(google_calendar.publish_local_events, local_events)


@router.get("/events")
def events(start: datetime, end: datetime, deleted: bool = False):
    if google_calendar.token_exists():
        return [] if deleted else run(google_calendar.list_events, start, end)
    return run(store.list_events, start, end, deleted=deleted)


@router.post("/events", status_code=201)
def create_event(data: store.EventInput):
    if google_calendar.token_exists():
        return run(google_calendar.create_event, data.model_dump(mode="json"))
    return run(store.write_event, "create", data=data.model_dump())


@router.get("/events/{event_id}")
def event(event_id: str):
    if google_calendar.token_exists():
        return run(google_calendar.get_event, event_id)
    return run(store.get_event, event_id)


@router.patch("/events/{event_id}")
def update_event(event_id: str, data: EventUpdate):
    if google_calendar.token_exists():
        return run(google_calendar.update_event, event_id, data.model_dump(exclude={"version"}, mode="json"))
    return run(store.write_event, "update", event_id=event_id, version=data.version,
               data=data.model_dump(exclude={"version"}))


@router.delete("/events/{event_id}")
def delete_event(event_id: str, version: int = Query(ge=1)):
    if google_calendar.token_exists():
        return run(google_calendar.delete_event, event_id)
    return run(store.write_event, "delete", event_id=event_id, version=version)


@router.post("/events/{event_id}/restore")
def restore_event(event_id: str, version: int = Query(ge=1)):
    if google_calendar.token_exists():
        raise HTTPException(409, "Gli eventi Google eliminati si recuperano da Google Calendar.")
    return run(store.write_event, "restore", event_id=event_id, version=version)


@router.get("/events/{event_id}/history")
def history(event_id: str):
    if google_calendar.token_exists():
        return []
    return run(store.event_history, event_id)


@router.get("/proposals")
def proposals():
    if google_calendar.token_exists():
        return []
    return run(store.list_proposals)


@router.post("/proposals/{proposal_id}/resolve")
def resolve(proposal_id: UUID, decision: Decision):
    if google_calendar.token_exists():
        raise HTTPException(409, "Le proposte agentiche verso Google Calendar saranno abilitate nel passo successivo.")
    return run(store.resolve_proposal, str(proposal_id), decision.approve)
