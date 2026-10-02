import asyncio
import json
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from core.runtime import runtime, TERMINAL
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
    return {"version": 1, "runs": runtime.snapshot(), "pool": pool_stats(), "workers": 1}

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
    try: return get_run(run_id)
    except (KeyError,ValueError) as error: raise HTTPException(404,"Run non trovato.") from error

@router.post("/runtime/runs/{run_id}/cancel")
def cancel(run_id: str):
    run = runtime.get(run_id)
    if run:
        run.stop()
        return run.snapshot()
    from core.run_lifecycle import request_cancel,RunConflict
    try: return request_cancel(run_id)
    except (RunConflict,ValueError) as error: raise HTTPException(409,str(error)) from error

@router.get("/runtime/runs/{run_id}/events")
async def events(run_id: str, request: Request, after: int = 0):
    run = require_run(run_id)
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


@router.post("/approvals/calendar/{approval_id}/resolve")
def calendar_decision(approval_id: UUID, data: Decision):
    try: return calendar.resolve_proposal(str(approval_id), data.approve)
    except KeyError as error: raise HTTPException(404, "Proposta non trovata.") from error
    except ValueError as error: raise HTTPException(409, str(error)) from error


@router.get("/runtime/runs")
def persisted_runs(limit: int = 100, status: str = ""):
    from core.run_lifecycle import list_runs
    return list_runs(limit,status)


@router.get("/runtime/components")
def component_states():
    from core.runtime_status import component_runtime_status
    return component_runtime_status()
