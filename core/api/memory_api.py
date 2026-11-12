"""Memory endpoints: permanent context, episodes, working memory and semantic memory."""
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.episodes import list_episodes
from core.memory import (
    MemoryConflict,
    delete_memory,
    memory_history,
    memory_stats,
    save_memory,
    search_memories,
)
from core.system_context import get_system_context, update_system_context
from core.working_memory import clear_working_memory, list_working_memory, set_working_memory

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
