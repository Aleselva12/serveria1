import asyncio
import json
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, ConfigDict
from starlette.responses import StreamingResponse
from core.runtime import runtime, TERMINAL
from core.run_states import DurabilityLost
from core.event_bus import bus
from core.database import pool_stats
from core.governance import list_approvals, resolve, capability_registry, approval_history
from core.permissions import set_policy
from core import calendar

router = APIRouter(prefix="/api/v1", tags=["Runtime"])

class Decision(BaseModel):
    approve: bool

class Policy(BaseModel):
    actor: str
    action: str
    policy: str


def require_run(identifier):
    run = runtime.get(identifier)
    if not run: raise HTTPException(404, "Run non presente nel runtime. Consulta le tracce persistenti.")
    return run

@router.get("/runtime")
def runtime_status():
    from core.execution_traces import trace_status
    return {"version": 3, "runs": runtime.snapshot(), "pool": pool_stats(), "workers": 1,"accepting_runs":not runtime.closed,"traces":trace_status(),
            'bus':{'process_id':bus.process_id,'sequence':bus.sequence,'capacity':bus.events.maxlen,'transport':'in_process'}}

@router.get("/runtime/registry")
def registry():
    return capability_registry()

@router.put("/runtime/policies")
def policy(data: Policy):
    try: set_policy(data.actor, data.action, data.policy)
    except (KeyError, ValueError) as error: raise HTTPException(422, str(error)) from error
    return {"saved": True}

@router.get("/runtime/runs/{run_id}")
def snapshot(run_id: str):
    live = runtime.get(run_id)
    if live: return live.snapshot()
    from core.run_lifecycle import get_run
    from core.run_lifecycle import persisted_snapshot
    try: return persisted_snapshot(get_run(run_id))
    except (KeyError,ValueError) as error: raise HTTPException(404,"Run non trovato.") from error

@router.post("/runtime/runs/{run_id}/cancel")
def cancel(run_id: str):
    from core.run_lifecycle import request_cancel, RunConflict, persisted_snapshot
    try:
        row = request_cancel(run_id)
        live = runtime.get(run_id)
        return live.snapshot() if live else persisted_snapshot(row)
    except (RunConflict,ValueError) as error: raise HTTPException(409,str(error)) from error
    except DurabilityLost as error: raise HTTPException(503,"Arresto richiesto localmente; stato persistente non confermato. Controlla Attività.") from error

@router.get("/runtime/runs/{run_id}/events")
async def events(run_id: str, request: Request, after: int = Query(0,ge=0), process_id: str | None = None):
    run = runtime.get(run_id)
    if not run:
        from core.run_lifecycle import get_run, persisted_snapshot
        try: archived = persisted_snapshot(get_run(run_id))
        except (KeyError,ValueError) as error: raise HTTPException(404,"Run non trovato.") from error
        if archived['status'] not in TERMINAL:
            raise HTTPException(409,"Run senza worker attivo. Verifica lo stato del backend.")
        async def archived_stream():
            yield "event: result\ndata: " + json.dumps(archived,ensure_ascii=False,default=str) + "\n\n"
        return StreamingResponse(archived_stream(),media_type='text/event-stream',headers={"Cache-Control":"no-cache"})
    async def stream():
        cursor = after
        origin = process_id
        last = request.headers.get('last-event-id')
        if last:
            try:
                origin,number = last.rsplit(':',1)
                UUID(origin)
                cursor = int(number)
                if cursor < 0: raise ValueError()
            except (ValueError,AttributeError):
                origin,cursor = 'invalid',0
        initial = not cursor or origin != bus.process_id
        while True:
            if await request.is_disconnected(): break
            batch, gap, watermark = bus.read_window(cursor,run_id)
            if initial or gap:
                # Same lock order as text producers: snapshot and cursor are one consistent boundary.
                with run.lock:
                    state = run.snapshot()
                    with bus.condition: cursor = bus.sequence
                yield 'id: '+bus.process_id+':'+str(cursor)+"\nevent: resync\ndata: " + json.dumps(state, default=str) + "\n\n"
                initial = False
                batch = []
            for event in batch:
                cursor = event["sequence"]
                yield "id: " + bus.process_id+':'+str(cursor) + "\ndata: " + json.dumps(event, ensure_ascii=False, default=str) + "\n\n"
            if batch or not gap: cursor = max(cursor,watermark)
            if run.done.is_set():
                yield "event: result\ndata: " + json.dumps(run.snapshot(), ensure_ascii=False, default=str) + "\n\n"
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(.2)
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get('/runtime/domain-events')
def domain_events(after: int = Query(0,ge=0),limit: int = Query(100,ge=1,le=500),run_id: UUID | None = None):
    from core.domain_events import read
    return {**read(after=after,limit=limit,run_id=str(run_id) if run_id else None),'guarantee':'transactional','executes_actions':False}


@router.get('/runtime/diagnostics')
def diagnostics(run_id: UUID | None = None,limit: int = Query(200,ge=1,le=500),before: UUID | None = None):
    from core.observability import read
    from core.domain_events import root_for
    from core.database import db_connection
    root = str(run_id) if run_id else None
    if root:
        with db_connection() as conn: root = root_for(conn,root)
        if not root: raise HTTPException(404,'Run non trovato.')
    try: return read(run_id=root,limit=limit,before=str(before) if before else None)
    except ValueError as error: raise HTTPException(409,str(error)) from error


@router.get('/runtime/event-contracts')
def event_contracts():
    from core.observability import PAYLOAD_FIELDS
    from core.protocol import ComponentEvent
    return {'version':1,'envelope':ComponentEvent.model_json_schema(),
            'diagnostic_types':{key:sorted(fields) for key,fields in PAYLOAD_FIELDS.items()},
            'critical_types':['run.committed','run.stop_requested','operation.committed','operation.reviewed'],
            'transient_types':['chat.delta','chat.reset'],'critical_cursor':'committed global sequence',
            'live_cursor':'process_id:sequence','commands':'TaskEnvelope via explicit ComponentBus.dispatch only'}

@router.get("/approvals")
def approvals():
    return {"generic": list_approvals(), "calendar": calendar.list_proposals(), "history": approval_history()}

@router.post("/approvals/{approval_id}/resolve")
def decision(approval_id: UUID, data: Decision, request: Request):
    try:
        run = runtime.submit("approval:" + str(approval_id), lambda run: resolve(str(approval_id), data.approve, request.state.user["username"]))
        return {"status": "queued", "run_id": run.id}
    except ValueError as error: raise HTTPException(409, str(error)) from error
    except RuntimeError as error: raise HTTPException(503,"Runtime non disponibile.") from error


@router.post("/approvals/calendar/{approval_id}/resolve")
def calendar_decision(approval_id: UUID, data: Decision):
    try: return calendar.resolve_proposal(str(approval_id), data.approve)
    except KeyError as error: raise HTTPException(404, "Proposta non trovata.") from error
    except ValueError as error: raise HTTPException(409, str(error)) from error


@router.get("/runtime/runs")
def persisted_runs(limit: int = 100, status: str = ""):
    from core.run_lifecycle import list_runs
    from core.run_lifecycle import persisted_snapshot
    try: return [persisted_snapshot(r) for r in list_runs(limit,status)]
    except ValueError as error: raise HTTPException(422,str(error)) from error


@router.get("/runtime/components")
def component_states():
    from core.runtime_status import component_runtime_status
    return component_runtime_status()


class OperationReview(BaseModel):
    model_config = ConfigDict(extra="forbid",strict=True)
    outcome: str
    note: str

@router.get('/runtime/operations')
def operations(limit: int = 100, run_id: UUID | None = None, unresolved: bool = False):
    from core.operation_journal import list_operations
    return list_operations(limit,str(run_id) if run_id else None,unresolved)

@router.post('/runtime/operations/{operation_id}/review')
def operation_review(operation_id: UUID, data: OperationReview, request: Request):
    from core.operation_journal import review
    try: return review(str(operation_id),data.outcome,data.note,request.state.user['username'])
    except ValueError as error: raise HTTPException(409,str(error)) from error
