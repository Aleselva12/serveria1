import asyncio
import json
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request
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
    return {"version": 2, "runs": runtime.snapshot(), "pool": pool_stats(), "workers": 1,"accepting_runs":not runtime.closed,"traces":trace_status()}

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
async def events(run_id: str, request: Request, after: int = 0):
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
        while True:
            if await request.is_disconnected(): break
            batch, gap = bus.read(cursor, run_id)
            if gap:
                yield "event: resync\ndata: " + json.dumps(run.snapshot(), default=str) + "\n\n"
            for event in batch:
                cursor = event["sequence"]
                yield "id: " + str(cursor) + "\ndata: " + json.dumps(event, ensure_ascii=False, default=str) + "\n\n"
            if run.done.is_set():
                yield "event: result\ndata: " + json.dumps(run.snapshot(), ensure_ascii=False, default=str) + "\n\n"
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(.2)
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

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
