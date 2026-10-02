import os
import uuid
import time
import asyncio
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import load_dotenv
from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.auth import AuthMiddleware, router as auth_router
from core.database import close_pool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.chat_store import conversation_stats, ensure_conversation, get_messages, list_conversations, recent_context, save_message, refresh_transcript
from core.database import database_status
from core.episodes import create_episode, list_episodes
from core.logging import logged_operation
from core.memory import delete_memory, memory_stats, save_memory, search_memories
from core.system_context import get_system_context, update_system_context
from core.working_memory import clear_working_memory, list_working_memory, set_working_memory
from core.calendar_api import router as calendar_router
from core.models import get_model_name
from core.monitoring import router as monitoring_router
from core.server_files import router as files_router
from core.ia_library import router as library_router
from core.registry import get_agents, get_registry
from graph import graph
from core.tool_inventory import inventory
from core.tool_definitions import definition
from core.automation_api import router as automation_router
from core.architecture_api import router as architecture_router, architecture_graph
from core.execution_traces import ExecutionTrace
from core.context_budget import prepare_context
from core.runtime import runtime, RunStopped, checkpoint
from core.runtime_api import router as runtime_router
from core.permissions_api import router as permissions_router
from concurrent.futures import ThreadPoolExecutor
from core.event_bus import bus
from fastapi import HTTPException, Request


load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11435").rstrip("/")

@asynccontextmanager
async def lifespan(app):
    from core import background_embeddings
    from core.runtime import recover_interrupted
    recover_interrupted()
    background_embeddings.start()
    yield
    runtime.shutdown()
    background_embeddings.stop()
    close_pool()


app = FastAPI(
    lifespan=lifespan,
    title="Cora API",
    version="0.1.0",
)

app.add_middleware(AuthMiddleware)
app.include_router(auth_router)
app.include_router(runtime_router)
app.include_router(permissions_router)
app.include_router(monitoring_router)
app.include_router(files_router)
app.include_router(library_router)
app.include_router(calendar_router)
app.include_router(architecture_router)
app.include_router(automation_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "CORA_UI_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=24000)
    thread_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    response: str
    thread_id: str
    run_id: str | None = None


class MemoryWriteRequest(BaseModel):
    memory_type: str
    key: str
    content: str
    source: str = "user_explicit"
    importance: int = 3
    expires_at: str | None = None
    metadata: dict = Field(default_factory=dict)


class SystemContextRequest(BaseModel):
    content: str
    metadata: dict = Field(default_factory=dict)


class WorkingMemoryRequest(BaseModel):
    state: dict = Field(default_factory=dict)
    ttl_minutes: int = 120


def _ollama_online() -> bool:
    try:
        with urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=1.5):
            return True
    except (URLError, TimeoutError, OSError):
        return False


@app.get("/health")
def health():
    database = database_status()
    return {
        "status": "ok",
        "ollama_online": _ollama_online(),
        "model": get_model_name("supervisor"),
        "agents": [agent["name"] for agent in get_agents()],
        "memory": memory_stats(),
        "database": database,
        "chat": conversation_stats() if database.get("reachable") else {
            "conversations": 0,
            "messages": 0,
        },
    }


@app.get("/tools/inventory")
def tools_inventory():
    return inventory(app.routes)


@app.get("/tools/definition")
def tools_definition(tool_id: str):
    from fastapi import HTTPException
    try:
        return definition(tool_id, app.routes)
    except KeyError as error:
        raise HTTPException(404, "Tool non trovato.") from error


@app.get("/capabilities")
def capabilities():
    return get_registry()


@app.get("/conversations")
def conversations(limit: int = 100, include_archived: bool = False):
    return list_conversations(limit=limit, include_archived=include_archived)


@app.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: str, limit: int = 500):
    return get_messages(conversation_id, limit=limit)


@app.get("/memory/context")
def read_system_context():
    return get_system_context()


@app.put("/memory/context")
def write_system_context(request: SystemContextRequest):
    return update_system_context(
        request.content,
        metadata={**request.metadata, "source": "user_settings"},
    )


@app.get("/memory/episodes")
def episodes(limit: int = 50):
    return list_episodes(limit=limit)


@app.get("/memory/working")
def working_memory():
    return list_working_memory()


@app.put("/memory/working/{agent_id}/{thread_id}")
def write_working_memory(agent_id: str, thread_id: str, request: WorkingMemoryRequest):
    return set_working_memory(
        agent_id=agent_id,
        thread_id=thread_id,
        state=request.state,
        ttl_minutes=request.ttl_minutes,
    )


@app.delete("/memory/working/{agent_id}/{thread_id}")
def remove_working_memory(agent_id: str, thread_id: str):
    return {"deleted": clear_working_memory(agent_id=agent_id, thread_id=thread_id)}


@app.get("/memory")
def memories(query: str = "", memory_type: str = "", limit: int = 50):
    return search_memories(query, memory_type=memory_type, limit=limit)


@app.get("/memory/stats")
def memory_status():
    return memory_stats()


@app.post("/memory")
def write_memory(request: MemoryWriteRequest):
    return save_memory(
        memory_type=request.memory_type,
        key=request.key,
        content=request.content,
        source=request.source,
        importance=request.importance,
        expires_at=request.expires_at,
        metadata=request.metadata,
    )


@app.delete("/memory/{memory_id}")
def remove_memory(memory_id: str):
    return {"deleted": delete_memory(memory_id)}


def execute_chat(request: ChatRequest, run):
    message = request.message.strip()
    if not message:
        return ChatResponse(
            response="Scrivi un messaggio per iniziare.",
            thread_id=run.thread_id,
        )

    thread_id = str(request.thread_id) if request.thread_id else run.thread_id
    ensure_conversation(thread_id)
    phase = time.perf_counter()
    user_message = save_message(
        conversation_id=thread_id,
        role="user",
        content=message,
        agent_id="user",
        metadata={"source": "chat_api", "run_id": run.id},
        refresh_transcript_now=False,
    )
    run.timings["user_save_ms"] = round((time.perf_counter()-phase)*1000,2)
    set_working_memory(
        agent_id="supervisor",
        thread_id=thread_id,
        state={
            "status": "running",
            "current_request": message,
            "last_user_message_id": str(user_message["id"]),
        },
    )

    with logged_operation(
        "chat_request",
        component="supervisor",
        thread_id=thread_id,
        data={
            "message_chars": len(message),
            "user_message_id": str(user_message["id"]),
        },
    ) as operation:
        trace = ExecutionTrace(thread_id, run.graph_version)
        phase = time.perf_counter()
        context = prepare_context(thread_id, callbacks=[trace])
        run.timings["context_ms"] = round((time.perf_counter()-phase)*1000,2)
        result = None
        model_span = None
        for mode, chunk in graph.stream({"messages": context}, config={"callbacks": [trace], "recursion_limit": 50}, stream_mode=["messages", "values"]):
            checkpoint()
            if mode == "values": result = chunk
            elif mode == "messages":
                token, metadata = chunk
                if metadata.get("langgraph_node") == "agent" and metadata.get("cora_role", "supervisor") == "supervisor":
                    span = metadata.get("langgraph_step")
                    if span != model_span:
                        model_span = span
                        run.output = ""
                        bus.publish("chat.reset", "supervisor", run_id=run.id, thread_id=thread_id)
                    if isinstance(token.content, str) and token.content:
                        run.output += token.content
                        bus.publish("chat.delta", "supervisor", run_id=run.id, thread_id=thread_id, payload={"text": token.content})
        checkpoint()
        if not result: raise RuntimeError("Grafo senza risultato.")
        phase = time.perf_counter()
        response = str(result["messages"][-1].content)
        assistant_message = save_message(
            conversation_id=thread_id,
            role="assistant",
            content=response,
            agent_id="supervisor",
            model_id=get_model_name("supervisor"),
            parent_message_id=str(user_message["id"]),
            metadata={"source": "chat_api", "run_id": run.id},
            refresh_transcript_now=False,
        )
        set_working_memory(
            agent_id="supervisor",
            thread_id=thread_id,
            state={
                "status": "completed",
                "current_request": message,
                "last_response": response[:1200],
                "last_user_message_id": str(user_message["id"]),
                "last_assistant_message_id": str(assistant_message["id"]),
            },
            ttl_minutes=120,
        )
        # Derived transcripts/episodes do not delay the persisted chat result.
        postprocess.submit(_postprocess_turn, thread_id, message, response, str(user_message["id"]), str(assistant_message["id"]))
        run.timings["result_save_ms"] = round((time.perf_counter()-phase)*1000,2)
        operation["result"] = {
            "response_chars": len(response),
            "assistant_message_id": str(assistant_message["id"]),
        }

    return ChatResponse(
        response=response,
        thread_id=thread_id,
        run_id=run.id,
    )


def submit_chat(request):
    thread_id = str(request.thread_id) if request.thread_id else str(uuid.uuid4())
    try:
        return runtime.submit(thread_id, lambda run: execute_chat(request, run).model_dump(), graph_version=architecture_graph()["version"])
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.post("/api/v1/chat/runs", status_code=202)
def start_chat(request: ChatRequest):
    return submit_chat(request).snapshot()


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request):
    run = submit_chat(request)
    while not run.done.is_set():
        if await http_request.is_disconnected(): run.stop()
        await asyncio.sleep(.1)
    if run.status in {"completed", "awaiting_approval"}: return run.result
    raise HTTPException(408 if run.status in {"cancelled", "timed_out"} else 500,
                        "Esecuzione " + run.status + ". Consulta Attività.")


postprocess = ThreadPoolExecutor(max_workers=1,thread_name_prefix="cora-postprocess")


def _postprocess_turn(thread_id,message,response,user_id,assistant_id):
    try:
        refresh_transcript(thread_id)
        create_episode(title=message.replace("\n", " ")[:80] or "Turno chat",
            summary="Richiesta: " + message[:240] + "\nRisultato: " + response[:420],
            conversation_id=thread_id,episode_type="conversation_turn",agent_id="supervisor",
            metadata={"user_message_id":user_id,"assistant_message_id":assistant_id})
    except Exception:
        pass  # Primary messages remain authoritative; derived copies can be rebuilt.
