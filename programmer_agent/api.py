"""Owner-only programmer endpoints; global AuthMiddleware protects this router."""
from __future__ import annotations
import json
import shutil
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from core.runtime import runtime, checkpoint, publish_text
from programmer_agent import workspace as ws
from programmer_agent import knowledge

router = APIRouter(prefix="/api/v1/programmer", tags=["Programmer"])


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkspaceCreate(StrictRequest):
    title: str = Field(min_length=1, max_length=120)


class FileWrite(StrictRequest):
    path: str = Field(min_length=1, max_length=300)
    content: str = Field(max_length=ws.MAX_FILE)
    expected_sha256: str = Field(default="", max_length=64)


class ProgrammerRequest(StrictRequest):
    workspace_id: UUID
    message: str = Field(min_length=1, max_length=12000)


class GraphImport(StrictRequest):
    graph: dict
    source_digest: str = Field(min_length=64, max_length=64)


class CheckRequest(StrictRequest):
    profile: str = "syntax"


class DraftImport(StrictRequest):
    path: str = Field(min_length=1, max_length=300)


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ws.WorkspaceConflict as error:
        raise HTTPException(409, str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(404, "Workspace o file non trovato.") from error
    except (ValueError, OSError) as error:
        raise HTTPException(422, str(error)) from error


@router.get("/status")
def status():
    from core.models import get_model_name
    return {"implemented": True, "model": get_model_name("programmer"), "skills": knowledge.SKILLS,
            "checks": {"syntax": True, "graphify_cli": bool(shutil.which("graphify")), "docker_cli": bool(shutil.which("docker")), "docker_environment_verified": False},
            "source_writes": False, "automatic_activation": False, "graph_provider": "Graphify"}


@router.get("/workspaces")
def workspaces():
    return call(ws.list_workspaces)


@router.post("/workspaces", status_code=201)
def create_workspace(data: WorkspaceCreate):
    return call(ws.create, data.title)


@router.get("/workspaces/{workspace_id}/files")
def files(workspace_id: UUID):
    return {"files": call(ws.list_files, str(workspace_id))}


@router.get("/workspaces/{workspace_id}/file")
def file(workspace_id: UUID, path: str, start_line: int = Query(1, ge=1), line_count: int = Query(120, ge=1, le=240), full: bool = False):
    if full:
        return call(ws.read_full, str(workspace_id), path)
    return call(ws.read, str(workspace_id), path, start_line, line_count)


@router.put("/workspaces/{workspace_id}/file")
def save_file(workspace_id: UUID, data: FileWrite):
    return call(ws.write, str(workspace_id), data.path, data.content, data.expected_sha256)


@router.get("/workspaces/{workspace_id}/diff")
def diff(workspace_id: UUID):
    return call(ws.diff, str(workspace_id))


@router.get("/workspaces/{workspace_id}/graph")
def graph_status(workspace_id: UUID):
    return call(knowledge.graph_status, str(workspace_id))


@router.post("/workspaces/{workspace_id}/graph")
def import_graph(workspace_id: UUID, data: GraphImport):
    return call(knowledge.import_graph, str(workspace_id), data.graph, data.source_digest)


@router.post("/workspaces/{workspace_id}/drafts", status_code=201)
def import_draft(workspace_id: UUID, data: DraftImport):
    """Explicit owner import into the existing graphical editor; never execution."""
    from core.automation_drafts import save_draft
    from core.tool_inventory import inventory
    identifier = str(workspace_id)
    path = call(ws.file_path, identifier, data.path)
    if not path.is_file():
        raise HTTPException(404, "File non trovato.")
    if path.suffix != ".json" or path.stat().st_size > ws.MAX_FILE:
        raise HTTPException(422, "Seleziona una bozza JSON valida.")
    value = call(json.loads, path.read_text(encoding="utf-8"))
    ids = {e["id"] for e in inventory()["entries"] if e["kind"] == "tool"}
    return call(save_draft, value, tool_ids=ids)


def execute_programmer(request: ProgrammerRequest, run) -> dict:
    from core.chat_store import ensure_conversation, save_message
    from core.context_budget import prepare_context
    from core.execution_traces import ExecutionTrace
    from core.models import get_model_name
    from core.runtime_context import bind_runtime
    from programmer_agent.programmer_graph import graph

    identifier = str(request.workspace_id)
    with ws.bind_workspace(identifier), bind_runtime(run.id, run.thread_id):
        ensure_conversation(run.thread_id, title="Programmatore · " + ws.manifest(identifier)["title"])
        user = save_message(conversation_id=run.thread_id, role="user", content=request.message,
                            agent_id="user", metadata={"source": "programmer_api", "workspace_id": identifier, "run_id": run.id},
                            refresh_transcript_now=False)
        trace = ExecutionTrace(run.thread_id, run.graph_version)
        messages = prepare_context(run.thread_id, callbacks=[trace])
        result = None
        run.agents["programmer_agent"] = "running"
        for mode, chunk in graph.stream({"messages": messages}, config={"callbacks": [trace], "recursion_limit": 60}, stream_mode=["messages", "values"]):
            checkpoint()
            if mode == "values":
                result = chunk
            elif mode == "messages":
                token, metadata = chunk
                if metadata.get("langgraph_node") == "call_llm":
                    publish_text(run, "programmer", ("programmer", token.id, metadata.get("langgraph_step")), token.content)
        checkpoint()
        if not result:
            raise RuntimeError("Programmatore senza risultato.")
        response = str(result["messages"][-1].content)
        save_message(conversation_id=run.thread_id, role="assistant", content=response, agent_id="programmer_agent",
                     model_id=get_model_name("programmer"), parent_message_id=str(user["id"]),
                     metadata={"source": "programmer_api", "workspace_id": identifier, "run_id": run.id}, refresh_transcript_now=False)
        return {"response": response, "thread_id": run.thread_id, "workspace_id": identifier, "run_id": run.id}


@router.post("/runs", status_code=202)
def start(data: ProgrammerRequest):
    identifier = str(data.workspace_id)
    call(ws.directory, identifier)
    if not data.message.strip():
        raise HTTPException(422, "Scrivi una richiesta.")
    try:
        # One stable conversation per workspace; reuses the global model queue and durable run lifecycle.
        run = runtime.submit(identifier, lambda run: execute_programmer(data, run), graph_version="programmer-v1", kind="programmer", target="programmer_agent")
        return run.snapshot()
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(503, "Runtime non disponibile. Consulta Attività.") from error


@router.post("/workspaces/{workspace_id}/checks", status_code=202)
def check(workspace_id: UUID, data: CheckRequest):
    from programmer_agent.checks import run_check
    identifier = str(workspace_id)
    call(ws.directory, identifier)
    if data.profile not in {"syntax", "contracts", "python_tests", "typescript", "frontend_build"}:
        raise HTTPException(422, "Profilo non disponibile.")
    def execute(run):
        result = run_check(identifier, data.profile)
        return {"response": json.dumps(result, ensure_ascii=False, indent=2), "thread_id": identifier, "workspace_id": identifier}
    try:
        return runtime.submit(identifier, execute, graph_version="programmer-checks-v1", kind="programmer_check", target="programmer_agent").snapshot()
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(503, "Runtime non disponibile.") from error


@router.post("/workspaces/{workspace_id}/graph/build", status_code=202)
def build_graph(workspace_id: UUID):
    from programmer_agent.build_graph import build
    identifier = str(workspace_id)
    call(ws.directory, identifier)
    def execute(run):
        result = build(identifier)
        return {"response": json.dumps(result, ensure_ascii=False, indent=2), "thread_id": identifier}
    try:
        return runtime.submit(identifier, execute, graph_version="programmer-graph-v1", kind="programmer_graph", target="programmer_agent").snapshot()
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(503, "Runtime non disponibile.") from error


class ComponentRequest(StrictRequest):
    title: str = Field(min_length=1, max_length=120)
    kind: str
    files: list[str] = Field(min_length=1, max_length=100)
    dependencies: list[str] = Field(default_factory=list, max_length=50)
    integration: str = Field(min_length=1, max_length=12000)
    component_id: str = ''


class ComponentTransition(StrictRequest):
    status: str
    note: str = Field(min_length=1, max_length=3000)
    expected_version: int = Field(ge=1)
    expected_digest: str = Field(min_length=64, max_length=64)


@router.get('/workspaces/{workspace_id}/components')
def components(workspace_id: UUID):
    from programmer_agent.components import listing
    return {'components': call(listing, str(workspace_id))}


@router.post('/workspaces/{workspace_id}/components', status_code=201)
def register_component(workspace_id: UUID, data: ComponentRequest):
    from programmer_agent.components import register
    return call(register, str(workspace_id), **data.model_dump())


@router.post('/workspaces/{workspace_id}/components/{component_id}/status')
def component_status(workspace_id: UUID, component_id: UUID, data: ComponentTransition):
    from programmer_agent.components import transition
    return call(transition, str(workspace_id), str(component_id), **data.model_dump())


@router.post('/workspaces/{workspace_id}/components/{component_id}/deliveries', status_code=201)
def delivery(workspace_id: UUID, component_id: UUID):
    from programmer_agent.components import deliver
    return call(deliver, str(workspace_id), str(component_id))


@router.get('/workspaces/{workspace_id}/deliveries/{delivery_id}')
def download_delivery(workspace_id: UUID, delivery_id: UUID):
    from fastapi.responses import FileResponse
    path = call(ws.directory, str(workspace_id)) / 'deliveries' / (str(delivery_id)+'.zip')
    call(ws._no_links, path)
    if not path.is_file():
        raise HTTPException(404, 'Consegna non trovata.')
    return FileResponse(path, media_type='application/zip', filename='cora-component-'+str(delivery_id)+'.zip')


@router.get('/workspaces/{workspace_id}/checks')
def check_history(workspace_id: UUID):
    from programmer_agent.components import check_history
    return {'checks': call(check_history, str(workspace_id))}


@router.get('/workspaces/{workspace_id}/graph/view')
def graph_view(workspace_id: UUID, query: str = Query('', max_length=200), node_id: str = Query('', max_length=500)):
    return call(knowledge.graph_view, str(workspace_id), query, node_id)
