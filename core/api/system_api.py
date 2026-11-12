"""Backend status, model selection, tool inventory and capability registry endpoints."""
from urllib.error import URLError

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.chat_store import conversation_stats
from core.database import database_status
from core.memory import memory_stats
from core.models import (
    RuntimeSettingsError,
    get_default_model_name,
    list_ollama_models,
    save_runtime_model,
)
from core.ollama_transport import get_ollama_base_url, urlopen
from core.registry import get_agents, get_registry
from core.runtime_profile import runtime_mode
from core.tool_definitions import definition
from core.tool_inventory import inventory

router = APIRouter()


class ModelSelectionRequest(BaseModel):
    model: str = Field(min_length=1, max_length=200)


def _ollama_online() -> bool:
    from core.agent_models import binding, remote_ready
    selected = binding('supervisor')
    if selected and selected['machine_id'] != 'local':
        return remote_ready(selected['machine_id'], selected['model'])
    try:
        with urlopen(f"{get_ollama_base_url()}/api/tags", timeout=1.5):
            return True
    except (URLError, TimeoutError, OSError):
        return False


@router.get("/health")
def health():
    from core.file_paths import library_workspace_status
    database = database_status()
    from core.api.machines_api import _find
    from core.models import resolve_model
    selected = resolve_model('supervisor')
    try:
        machine_name = 'Ollama di Cora' if selected['machine_id'] == 'local' else _find(selected['machine_id'])['name']
    except HTTPException:
        machine_name = 'Worker non registrato'
    return {
        "status": "ok",
        "library": library_workspace_status(),
        "ollama_online": _ollama_online(),
        "model": selected['model'],
        "model_machine": machine_name,
        "model_source": selected['source'],
        "model_configuration_id": selected['configuration_id'],
        "runtime_mode": runtime_mode(),
        "agents": [agent["name"] for agent in get_agents()],
        "memory": memory_stats(),
        "database": database,
        "chat": conversation_stats() if database.get("reachable") else {
            "conversations": 0,
            "messages": 0,
        },
    }


@router.get("/runtime/configuration")
def runtime_configuration():
    from core.models import performance_configuration
    return performance_configuration("supervisor")


@router.get("/runtime/models")
def runtime_models():
    try:
        models = list_ollama_models()
    except Exception as error:
        raise HTTPException(503, "Ollama non raggiungibile.") from error
    return {"active": get_default_model_name("supervisor"), "models": models}


@router.put("/runtime/model")
def select_runtime_model(request: ModelSelectionRequest):
    try:
        models = list_ollama_models()
        save_runtime_model(request.model, models=models)
    except RuntimeSettingsError as error:
        raise HTTPException(500, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except Exception as error:
        raise HTTPException(503, "Ollama non raggiungibile.") from error
    return {"active": get_default_model_name("supervisor"), "models": models}


# The inventory describes the whole application, so these two read the routes of the
# app serving the request instead of importing api (which would be a cycle).
@router.get("/tools/inventory")
def tools_inventory(request: Request):
    return inventory(request.app.routes)


@router.get("/tools/definition")
def tools_definition(tool_id: str, request: Request):
    try:
        return definition(tool_id, request.app.routes)
    except KeyError as error:
        raise HTTPException(404, "Tool non trovato.") from error


@router.get("/capabilities")
def capabilities():
    return get_registry()
