from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import automation_drafts as store
from core.access import owner_dependency
from core.tool_inventory import inventory

router = APIRouter(
    prefix="/tools/drafts",
    tags=["Automation drafts"],
    dependencies=[Depends(owner_dependency("automation"))],
)


class DraftInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    nodes: list[dict] = Field(min_length=1, max_length=80)
    edges: list[dict] = Field(max_length=160)
    version: int | None = Field(default=None, ge=1)


def _run(fn):
    try:
        return fn()
    except store.VersionConflict as error:
        raise HTTPException(409, str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(404, "Bozza non trovata.") from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except OSError as error:
        raise HTTPException(503, "Archivio delle bozze non disponibile.") from error


@router.get("")
def list_drafts():
    return _run(store.list_drafts)


@router.get("/{draft_id}")
def get_draft(draft_id: str):
    return _run(lambda: store.get_draft(draft_id))


def _save(body, request, draft_id=None):
    tool_ids = {e["id"] for e in inventory(request.app.routes)["entries"] if e["kind"] != "planned"}
    return _run(lambda: store.save_draft(body.model_dump(), draft_id, body.version, tool_ids=tool_ids))


@router.post("", status_code=201)
def create_draft(body: DraftInput, request: Request):
    return _save(body, request)


@router.put("/{draft_id}")
def update_draft(draft_id: str, body: DraftInput, request: Request):
    return _save(body, request, draft_id)
