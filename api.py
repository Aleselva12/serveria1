import os
import uuid
import time
import asyncio
from urllib.error import URLError
from core.ollama_transport import urlopen, get_ollama_base_url

from dotenv import load_dotenv
from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.auth import AuthMiddleware, router as auth_router
from core.desktop_updates import router as update_router
from core.database import close_pool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal

from core.chat_store import conversation_stats, ensure_conversation, get_messages, list_conversations, recent_context, save_message, refresh_transcript
from core.database import database_status
from core.episodes import create_episode, list_episodes
from core.logging import logged_operation
from core.memory import delete_memory, memory_stats, save_memory, search_memories, memory_history, MemoryConflict
from core.system_context import get_system_context, update_system_context
from core.working_memory import clear_working_memory, list_working_memory, set_working_memory
from core.calendar_api import router as calendar_router
from core.models import get_model_name, list_ollama_models, save_runtime_model, RuntimeSettingsError
from core.runtime_profile import validate_runtime_profile, runtime_mode
from core.monitoring import router as monitoring_router
from core.server_files import router as files_router
from core.ia_library import router as library_router
from core.chat_attachments import router as attachments_router, attachment_rows, request_content, public as attachment_public
from core.audio_api import router as audio_router
from core.registry import get_agents, get_registry
from graph import graph
from core.tool_inventory import inventory
from core.tool_definitions import definition
from core.automation_api import router as automation_router
from core.architecture_api import router as architecture_router, architecture_graph
from core.execution_traces import ExecutionTrace
from core.context_budget import prepare_context, schedule_summary
from core.runtime import runtime, RunStopped, checkpoint, publish_text
from core.runtime_api import router as runtime_router
from core.permissions_api import router as permissions_router
from programmer_agent.api import router as programmer_router
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException, Request


load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")


@asynccontextmanager
async def lifespan(app):
    validate_runtime_profile()
    from core import background_embeddings
    from core.runtime import recover_interrupted
    recover_interrupted()
    from core.observability import archive
    archive.start()
    background_embeddings.start()
    from core import library_monitor
    library_monitor.start()
    yield
    runtime.shutdown()
    library_monitor.stop()
    background_embeddings.stop()
    archive.stop()
    close_pool()


app = FastAPI(
    lifespan=lifespan,
    title="Cora API",
    version="0.1.0",
)

app.add_middleware(AuthMiddleware)
app.include_router(auth_router)
app.include_router(update_router)
app.include_router(runtime_router)
app.include_router(permissions_router)
app.include_router(monitoring_router)
app.include_router(files_router)
app.include_router(library_router)
app.include_router(attachments_router)
app.include_router(audio_router)
app.include_router(calendar_router)
app.include_router(architecture_router)
app.include_router(automation_router)
app.include_router(programmer_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "CORA_UI_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from core.generation_policy import ResponseLength


class ChatRequest(BaseModel):
    response_length: ResponseLength = "medium"
    message: str = Field(min_length=1, max_length=24000)
    thread_id: uuid.UUID | None = None
    attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=6)
    manual_tools: list[str] | None = Field(default=None, max_length=30)


class ChatResponse(BaseModel):
    response: str
    thread_id: str
    run_id: str | None = None


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


class ModelSelectionRequest(BaseModel):
    model: str = Field(min_length=1, max_length=200)


class WorkingMemoryRequest(BaseModel):
    state: dict = Field(default_factory=dict)
    ttl_minutes: int = 120


def _ollama_online() -> bool:
    try:
        with urlopen(f"{get_ollama_base_url()}/api/tags", timeout=1.5):
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
        "runtime_mode": runtime_mode(),
        "agents": [agent["name"] for agent in get_agents()],
        "memory": memory_stats(),
        "database": database,
        "chat": conversation_stats() if database.get("reachable") else {
            "conversations": 0,
            "messages": 0,
        },
    }


@app.get("/runtime/models")
def runtime_models():
    try:
        models = list_ollama_models()
    except Exception as error:
        raise HTTPException(503, "Ollama non raggiungibile.") from error
    return {"active": get_model_name("supervisor"), "models": models}


@app.put("/runtime/model")
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
    return {"active": get_model_name("supervisor"), "models": models}


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
    try:
        return update_system_context(request.content, expected_version=request.expected_version,
            metadata={**request.metadata, "source": "user_settings"})
    except MemoryConflict as error:
        raise HTTPException(409,str(error)) from error


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
def memories(query: str = "", memory_type: str = "", limit: int = 50, include_expired: bool = False):
    return search_memories(query, memory_type=memory_type, limit=limit,include_expired=include_expired)


@app.get("/memory/stats")
def memory_status():
    return memory_stats()


@app.post("/memory")
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


@app.get("/memory/{memory_id}/history")
def read_memory_history(memory_id: uuid.UUID, limit: int = 50):
    return memory_history(str(memory_id),limit=limit)


@app.delete("/memory/{memory_id}")
def remove_memory(memory_id: str):
    return {"deleted": delete_memory(memory_id)}


def execute_chat(request: ChatRequest, run):
    message = request.message.strip()
    attachments = attachment_rows(run.thread_id, request.attachment_ids) if request.attachment_ids else []
    enriched_message = request_content(message, attachments)
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
        content=enriched_message,
        agent_id="user",
        metadata={"source": "chat_api", "run_id": run.id, "display_content": message, "attachments": [attachment_public(row) for row in attachments]},
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
        for mode, chunk in graph.stream({"messages": context, "request_text": message, "manual_tools": request.manual_tools, "response_length": request.response_length}, config={"callbacks": [trace], "recursion_limit": 50}, stream_mode=["messages", "values"]):
            checkpoint()
            if mode == "values": result = chunk
            elif mode == "messages":
                token, metadata = chunk
                if metadata.get("langgraph_node") == "agent":
                    role = metadata.get("cora_role", "supervisor")
                    span = ("root", role, token.id, metadata.get("langgraph_step"))
                    publish_text(run, role, span, token.content)
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
            "response_char…23904 tokens truncated…xEmit.ReactJSX}}).outputText
 .replace(/from "react\/jsx-runtime"/g,'from '+external('react/jsx-runtime'))
 .replace(/from "react"/g,'from '+external('react'))
 .replace('import { apiBaseUrl } from "../services/api";','const apiBaseUrl="/backend";')
 .replace('import { authenticatedFetch } from "../services/transport";','const authenticatedFetch=(...args)=>globalThis.__updateFetch(...args);');
const Panel=(await import('data:text/javascript;base64,'+Buffer.from(c).toString('base64'))).default;
const text=n=>typeof n==='string'?n:(n?.children||[]).map(text).join(' ');
const button=(r,label)=>r.root.findAllByType('button').find(b=>text(b).includes(label));

test('Windows preparation is explicit and ready never means installed',async()=>{
 let calls=[],status='idle',r;
 globalThis.__updateFetch=async(path,init={})=>{
  calls.push([path,init.method||'GET']);
  if(init.method==='POST')status='ready';
  return {ok:true,json:async()=>({platform:'windows',status,commit:'abc',directory:'C:/candidate'})};
 };
 try{
  await act(async()=>{r=create(React.createElement(Panel));});
  assert.equal(calls.length,0);
  await act(async()=>button(r,'Aggiorna Cora').props.onClick());
  assert.equal(calls.length,1); assert.equal(r.root.findAllByType('a').length,0);
  await act(async()=>button(r,'Prepara aggiornamento Windows').props.onClick());
  assert.equal(calls.filter(c=>c[1]==='POST').length,1);
  assert.match(text(r.toJSON()),/preparato, non installato/);
  assert.match(text(r.toJSON()),/backup PostgreSQL/);
 }finally{if(r)await act(async()=>r.unmount());}
});

test('Debian uses its configured URL and explains an absent service',async()=>{
 for(const url of ['', 'https://server.example/update']){
  globalThis.__updateFetch=async()=>({ok:true,json:async()=>({platform:'server',status:url?'configured':'unconfigured',url})});
  let r;try{
   await act(async()=>{r=create(React.createElement(Panel));});
   await act(async()=>button(r,'Aggiorna Cora').props.onClick());
   assert.equal(Boolean(button(r,'Prepara aggiornamento Windows')),false);
   if(url)assert.equal(r.root.findByType('a').props.href,url);
   else assert.match(text(r.toJSON()),/CORA_UPDATE_URL/);
  }finally{if(r)await act(async()=>r.unmount());}
 }
});

test('an uncertain POST is never repeated automatically and remains visible',async()=>{
 let posts=0,r;
 globalThis.__updateFetch=async(path,init={})=>{
  if(init.method==='POST'){posts++;throw Error('offline');}
  return {ok:true,json:async()=>({platform:'windows',status:'idle'})};
 };
 try{
  await act(async()=>{r=create(React.createElement(Panel));});
  await act(async()=>button(r,'Aggiorna Cora').props.onClick());
  await act(async()=>button(r,'Prepara aggiornamento Windows').props.onClick());
  assert.equal(posts,1);assert.match(text(r.toJSON()),/offline/);
 }finally{if(r)await act(async()=>r.unmount());}
});
