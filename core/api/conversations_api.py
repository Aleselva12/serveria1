"""Conversation and conversation-project endpoints used by the chat sidebar."""
import uuid

from fastapi import APIRouter, HTTPException
from psycopg.errors import ForeignKeyViolation
from pydantic import BaseModel, Field

from core.chat_store import (
    archive_conversation,
    delete_conversation,
    ensure_conversation,
    get_messages,
    list_conversations,
    move_conversation,
    rename_conversation,
)
from core.conversation_projects import (
    create_project,
    delete_project,
    list_projects,
    update_project,
)

router = APIRouter()


class ConversationCreateRequest(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID | None = None


class ConversationUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    archived: bool | None = None
    project_id: uuid.UUID | None = None
    clear_project: bool = False


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    shared_context: str = Field(default="", max_length=12000)


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    shared_context: str | None = Field(default=None, max_length=12000)


@router.get("/conversations")
def conversations(limit: int = 100, include_archived: bool = False):
    return list_conversations(limit=limit, include_archived=include_archived)


@router.post("/conversations")
def create_conversation(request: ConversationCreateRequest):
    try:
        return ensure_conversation(
            str(request.id),
            project_id=str(request.project_id) if request.project_id else None,
        )
    except ValueError as error:
        raise HTTPException(422, "Identificativo conversazione o progetto non valido.") from error
    except ForeignKeyViolation as error:
        raise HTTPException(422, "Progetto inesistente o non valido.") from error
    except Exception as error:
        # Internal/DB errors are not invalid client parameters; never disclose SQL details.
        raise HTTPException(500, "Creazione conversazione non riuscita.") from error


@router.patch("/conversations/{conversation_id}")
def update_conversation(conversation_id: str, request: ConversationUpdateRequest):
    try:
        row = None
        if request.title is not None:
            row = rename_conversation(conversation_id, request.title)
        if request.archived is not None:
            row = archive_conversation(conversation_id, request.archived)
        if request.project_id is not None or request.clear_project:
            row = move_conversation(
                conversation_id,
                None if request.clear_project else str(request.project_id),
            )
        if row is None:
            rows = [
                item
                for item in list_conversations(limit=500, include_archived=True)
                if str(item["id"]) == conversation_id
            ]
            if not rows:
                raise KeyError(conversation_id)
            row = rows[0]
        return row
    except KeyError as error:
        raise HTTPException(404, "Conversazione o progetto non trovato.") from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.delete("/conversations/{conversation_id}")
def remove_conversation(conversation_id: str):
    if not delete_conversation(conversation_id):
        raise HTTPException(404, "Conversazione non trovata.")
    return {"deleted": True}


@router.get("/conversation-projects")
def conversation_projects():
    return list_projects()


@router.post("/conversation-projects")
def add_conversation_project(request: ProjectCreateRequest):
    return create_project(request.name, request.shared_context)


@router.patch("/conversation-projects/{project_id}")
def edit_conversation_project(project_id: str, request: ProjectUpdateRequest):
    try:
        return update_project(
            project_id,
            name=request.name,
            shared_context=request.shared_context,
        )
    except KeyError as error:
        raise HTTPException(404, "Progetto non trovato.") from error


@router.delete("/conversation-projects/{project_id}")
def remove_conversation_project(project_id: str):
    if not delete_project(project_id):
        raise HTTPException(404, "Progetto non trovato.")
    return {"deleted": True}


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: str, limit: int = 500):
    return get_messages(conversation_id, limit=limit)
