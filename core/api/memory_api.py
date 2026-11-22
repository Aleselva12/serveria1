"""Memory endpoints: permanent context, episodes, working memory and semantic memory."""
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.domain.chat_store import get_messages
from core.domain.episodes import list_episodes
from core.domain.memory import (
    MemoryConflict,
    delete_memory,
    memory_history,
    memory_stats,
    save_memory,
    search_memories,
)
from core.domain.memory_library import (
    CardCreate,
    CardEdit,
    CardState,
    Scope,
    StarterDrafts,
    export_cards,
    get_card,
    import_drafts,
    list_cards,
    list_scopes,
    save_card,
)
from core.domain.system_context import get_system_context, update_system_context
from core.domain.working_memory import clear_working_memory, list_working_memory, set_working_memory
from core.infra.domain_events import read as read_domain_events
from core.infra.run_lifecycle import get_run, list_runs

router = APIRouter()


class MemoryWriteRequest(BaseModel):
    memory_type: str
    key: str = Field(min_length=1,max_length=200)
    content: str = Field(min_length=1,max_length=12000)
    source: str = "user_explicit"
    importance: int = Field(default=3,ge=1,le=5)
    expires_at: str | None = None
    metadata: dict = Field(default_factory=dict)
    assertion: Literal['user_statement','observation','inference','unclassified'] = "user_statement"
    confidence: float | None = Field(default=None, ge=0, le=1)
    expected_version: int = Field(default=0, ge=0)
    expected_memory_id: uuid.UUID | None = None


class SystemContextRequest(BaseModel):
    content: str = Field(max_length=12000)
    metadata: dict = Field(default_factory=dict)
    expected_version: int = Field(ge=1)


class WorkingMemoryRequest(BaseModel):
    state: dict = Field(default_factory=dict)
    ttl_minutes: int = 120


@router.get("/memory/context")
def read_system_context():
    return get_system_context()


@router.put("/memory/context")
def write_system_context(request: SystemContextRequest):
    try:
        return update_system_context(request.content, expected_version=request.expected_version,
            metadata={**request.metadata, "source": "user_settings"})
    except MemoryConflict as error:
        raise HTTPException(409,str(error)) from error


@router.get("/memory/episodes")
def episodes(limit: int = 50):
    return list_episodes(limit=limit)


@router.get("/memory/working")
def working_memory():
    return list_working_memory()


@router.put("/memory/working/{agent_id}/{thread_id}")
def write_working_memory(agent_id: str, thread_id: str, request: WorkingMemoryRequest):
    return set_working_memory(
        agent_id=agent_id,
        thread_id=thread_id,
        state=request.state,
        ttl_minutes=request.ttl_minutes,
    )


@router.delete("/memory/working/{agent_id}/{thread_id}")
def remove_working_memory(agent_id: str, thread_id: str):
    return {"deleted": clear_working_memory(agent_id=agent_id, thread_id=thread_id)}


@router.get("/memory")
def memories(query: str = "", memory_type: str = "", limit: int = 50, include_expired: bool = False):
    return search_memories(query, memory_type=memory_type, limit=limit,include_expired=include_expired)


@router.get("/memory/stats")
def memory_status():
    return memory_stats()


@router.post("/memory")
def write_memory(request: MemoryWriteRequest):
    try:
        return save_memory(
            memory_type=request.memory_type,
            key=request.key,
            content=request.content,
            source="user_explicit",
            importance=request.importance,
            expires_at=request.expires_at,
            metadata=request.metadata,
            assertion=request.assertion, confidence=request.confidence,
            expected_version=request.expected_version, editor="user",
            expected_memory_id=str(request.expected_memory_id) if request.expected_memory_id else None,
        )
    except MemoryConflict as error:
        raise HTTPException(409,str(error)) from error
    except ValueError as error:
        raise HTTPException(422,str(error)) from error


@router.get("/memory/{memory_id}/history")
def read_memory_history(memory_id: uuid.UUID, limit: int = 50):
    return memory_history(str(memory_id),limit=limit)


@router.delete("/memory/{memory_id}")
def remove_memory(memory_id: str):
    return {"deleted": delete_memory(memory_id)}


@router.get("/memory/evidence/runs")
def evidence_runs(limit: int = Query(30, ge=1, le=100)):
    return [
        {field: run[field] for field in ("id", "kind", "target", "status", "created_at")}
        for run in list_runs(limit=limit)
    ]


@router.get("/memory/evidence/runs/{run_id}")
def run_evidence(
    run_id: uuid.UUID,
    after: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    try:
        run = get_run(str(run_id))
    except KeyError as error:
        raise HTTPException(404, "Esecuzione non trovata") from error

    try:
        conversation_id = str(uuid.UUID(str(run["thread_id"])))
    except ValueError:
        conversation_id = None
    messages = get_messages(conversation_id, run_id=run_id) if conversation_id else []
    saved_episodes = list_episodes(limit=1, run_id=run_id)
    episode = saved_episodes[0] if saved_episodes else None
    return {
        "run_id": run_id,
        "thread_id": run["thread_id"],
        "report": {
            "kind": run["kind"], "target": run["target"], "status": run["status"],
            "created_at": run["created_at"], "finished_at": run["finished_at"],
            "error_type": run["error_type"],
            "episode": {field: episode[field] for field in ("id", "title", "summary")} if episode else None,
        },
        "messages": [
            {field: message[field] for field in ("id", "role", "content", "created_at")}
            for message in messages
        ],
        **read_domain_events(run_id=str(run_id), after=after, limit=limit),
    }


@router.get("/memory/library/scopes")
def library_scopes(after: str = Query("", max_length=182), limit: int = Query(50, ge=1, le=100)):
    return list_scopes(after, limit)


@router.get("/memory/library")
def library(
    scope: Scope = "global",
    query: str = Query("", max_length=200),
    state: CardState | None = None,
    after: str = Query("", max_length=60),
    limit: int = Query(50, ge=1, le=100),
):
    return list_cards(scope, query, state or "", after, limit)


@router.get("/memory/library/export")
def library_export(
    scope: Scope = "global",
    after: str = Query("", max_length=60),
    limit: int = Query(20, ge=1, le=50),
):
    cards = export_cards(scope, after=after, limit=limit)
    return {
        "format": "serveria-memory-library-v1", "scope": scope, "cards": cards,
        "next_cursor": cards[-1]["slug"] if len(cards) == limit else None,
    }


@router.get("/memory/library/cards/{card_id}")
def library_card(card_id: uuid.UUID, version: int | None = Query(None, ge=1)):
    try:
        return get_card(card_id, version)
    except KeyError as error:
        raise HTTPException(404, "Scheda o revisione non trovata") from error


def _save_library_card(document: CardCreate | CardEdit, card_id: uuid.UUID | None = None):
    try:
        return save_card(document, card_id)
    except KeyError as error:
        raise HTTPException(404, "Scheda non trovata") from error
    except MemoryConflict as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/memory/library/cards", status_code=201)
def create_library_card(document: CardCreate):
    return _save_library_card(document)


@router.put("/memory/library/cards/{card_id}")
def edit_library_card(card_id: uuid.UUID, document: CardEdit):
    return _save_library_card(document, card_id)


@router.post("/memory/library/drafts", status_code=201)
def import_library_drafts(drafts: StarterDrafts):
    try:
        return import_drafts(drafts)
    except MemoryConflict as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
