from datetime import datetime
from uuid import UUID
import hmac
import os

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from psycopg import OperationalError

from core import calendar as store
from core.server_files import is_loopback


def calendar_owner(request: Request):
    token = os.getenv("CORA_CALENDAR_TOKEN", "")
    if token:
        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied.encode(), ("Bearer " + token).encode()):
            raise HTTPException(401, "Token calendario non valido.")
    elif not is_loopback(request.client.host if request.client else ""):
        raise HTTPException(403, "Configura CORA_CALENDAR_TOKEN per l'accesso remoto.")


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
    except (OperationalError, RuntimeError) as error:
        raise HTTPException(503, "Calendario non disponibile: verifica PostgreSQL e CORA_DATABASE_URL.") from error


@router.get("/events")
def events(start: datetime, end: datetime, deleted: bool = False):
    return run(store.list_events, start, end, deleted=deleted)


@router.post("/events", status_code=201)
def create_event(data: store.EventInput):
    return run(store.write_event, "create", data=data.model_dump())


@router.get("/events/{event_id}")
def event(event_id: UUID):
    return run(store.get_event, str(event_id))


@router.patch("/events/{event_id}")
def update_event(event_id: UUID, data: EventUpdate):
    return run(store.write_event, "update", event_id=str(event_id), version=data.version,
               data=data.model_dump(exclude={"version"}))


@router.delete("/events/{event_id}")
def delete_event(event_id: UUID, version: int = Query(ge=1)):
    return run(store.write_event, "delete", event_id=str(event_id), version=version)


@router.post("/events/{event_id}/restore")
def restore_event(event_id: UUID, version: int = Query(ge=1)):
    return run(store.write_event, "restore", event_id=str(event_id), version=version)


@router.get("/events/{event_id}/history")
def history(event_id: UUID):
    return run(store.event_history, str(event_id))


@router.get("/proposals")
def proposals():
    return run(store.list_proposals)


@router.post("/proposals/{proposal_id}/resolve")
def resolve(proposal_id: UUID, decision: Decision):
    return run(store.resolve_proposal, str(proposal_id), decision.approve)
