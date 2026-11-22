from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from core.access import owner_dependency
from core.domain import automation_drafts as store
from core.domain import automation_runs as runs
from core.domain import automation_schedule as schedules
from core.tool_inventory import inventory

router = APIRouter(
    prefix="/tools/drafts",
    tags=["Automation drafts"],
    dependencies=[Depends(owner_dependency("automation"))],
)
runs_router = APIRouter(
    prefix="/tools/runs",
    tags=["Automation runs"],
    dependencies=[Depends(owner_dependency("automation"))],
)
schedules_router = APIRouter(
    prefix="/tools/schedules",
    tags=["Automation schedules"],
    dependencies=[Depends(owner_dependency("automation"))],
)


class RunInput(BaseModel):
    version: int = Field(ge=1)
    mode: Literal["dry_run", "live"]
    input: dict = Field(default_factory=dict)


class DraftInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    nodes: list[dict] = Field(min_length=1, max_length=80)
    edges: list[dict] = Field(max_length=160)
    version: int | None = Field(default=None, ge=1)


def _run(fn):
    try:
        return fn()
    except runs.RunRejected as error:
        raise HTTPException(422, {"message": str(error), "problems": error.problems}) from error
    except store.VersionConflict as error:
        raise HTTPException(409, str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(404, "Bozza non trovata.") from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except OSError as error:
        raise HTTPException(503, "Archivio delle bozze non disponibile.") from error


def _catalog(request):
    """Tool ids accepted in drafts and the input schema of those with an execution contract."""
    tool_ids, schemas = set(), {}
    for entry in inventory(request.app.routes)["entries"]:
        if entry["kind"] == "planned":
            continue
        tool_ids.add(entry["id"])
        capabilities = entry.get("capabilities") or []
        if capabilities:
            schemas[entry["id"]] = capabilities[0].get("input_schema") or {}
    return tool_ids, schemas


@router.get("")
def list_drafts():
    return _run(store.list_drafts)


# Declared before /{draft_id} routes so "validate" is never read as an id.
@router.post("/validate")
def validate_draft(body: DraftInput, request: Request):
    """Check a graph without saving it. Structural errors return 400, gaps return warnings."""
    tool_ids, schemas = _catalog(request)
    result = _run(lambda: store.validate_graph(body.model_dump(), tool_ids, schemas))
    return {"warnings": result["warnings"]}


@router.get("/{draft_id}")
def get_draft(draft_id: str):
    return _run(lambda: store.get_draft(draft_id))


def _save(body, request, draft_id=None):
    tool_ids, schemas = _catalog(request)
    return _run(lambda: store.save_draft(body.model_dump(), draft_id, body.version, tool_ids=tool_ids, tool_schemas=schemas))


@router.post("", status_code=201)
def create_draft(body: DraftInput, request: Request):
    return _save(body, request)


@router.put("/{draft_id}")
def update_draft(draft_id: str, body: DraftInput, request: Request):
    return _save(body, request, draft_id)


@router.delete("/{draft_id}", status_code=204)
def delete_draft(draft_id: str, version: int = Query(ge=1)):
    _run(lambda: store.delete_draft(draft_id, version))


@router.post("/{draft_id}/duplicate", status_code=201)
def duplicate_draft(draft_id: str, request: Request):
    tool_ids, schemas = _catalog(request)
    return _run(lambda: store.duplicate_draft(draft_id, tool_ids=tool_ids, tool_schemas=schemas))


@router.post("/{draft_id}/runs", status_code=201)
def start_run(draft_id: str, body: RunInput, request: Request):
    """Queue a manual run of the saved version the owner is looking at."""
    if not runs.runner_active():
        raise HTTPException(503, "Esecutore non attivo in questo processo.")
    bindings = runs.bindings_from_inventory(inventory(request.app.routes)["entries"])
    return _run(lambda: runs.create_run(draft_id, body.version, body.mode, body.input, bindings))


@router.get("/{draft_id}/runs")
def list_runs(draft_id: str):
    return _run(lambda: (store.get_draft(draft_id), runs.list_runs(draft_id))[1])


@runs_router.get("/{run_id}")
def get_run(run_id: str):
    return _run(lambda: runs.get_run(run_id))


@runs_router.post("/{run_id}/cancel")
def cancel_run(run_id: str):
    return _run(lambda: runs.cancel_run(run_id))


@schedules_router.get("")
def list_schedules():
    """Scheduled drafts, their next start and the outcome of the last slot."""
    return _run(lambda: {"runner_active": runs.runner_active(), "schedules": schedules.overview()})
