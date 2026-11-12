import asyncio
import os
import time
import uuid
from contextlib import ExitStack, asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.api.architecture_api import architecture_graph
from core.api.architecture_api import router as architecture_router
from core.api.audio_api import router as audio_router
from core.api.automation_api import router as automation_router
from core.api.calendar_api import router as calendar_router
from core.api.conversations_api import router as conversations_router
from core.api.machines_api import router as machines_router
from core.api.managed_apps_api import router as managed_apps_router
from core.api.memory_api import router as memory_router
from core.api.orchestration_api import router as orchestration_router
from core.api.permissions_api import router as permissions_router
from core.api.roadmap_classifier_api import router as roadmap_classifier_router
from core.api.runtime_api import router as runtime_router
from core.api.system_api import router as system_router
from core.auth import AuthMiddleware
from core.auth import router as auth_router
from core.context_budget import prepare_context, schedule_summary
from core.desktop_updates import router as update_router
from core.domain.chat_attachments import attachment_rows, request_content
from core.domain.chat_attachments import public as attachment_public
from core.domain.chat_attachments import router as attachments_router
from core.domain.chat_store import (
    ensure_conversation,
    refresh_transcript,
    save_message,
)
from core.domain.chat_store import (
    recent_context as recent_context,
)
from core.domain.episodes import create_episode
from core.domain.ia_library import router as library_router
from core.domain.notifications import router as notifications_router
from core.domain.notifications import worker as notification_worker
from core.domain.server_files import router as files_router
from core.domain.working_memory import set_working_memory
from core.infra.database import close_pool
from core.infra.execution_traces import ExecutionTrace
from core.infra.logging import logged_operation
from core.models import (
    get_model_name as get_model_name,
)
from core.monitoring import router as monitoring_router
from core.postprocessing import Postprocessing
from core.runtime import RunStopped as RunStopped
from core.runtime import checkpoint, publish_text, runtime
from core.runtime_profile import validate_runtime_profile
from core.verify.node_verification import router as node_verification_router
from core.verify.project_checks import router as project_checks_router
from graph import graph
from programmer_agent.api import router as programmer_router

load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")


@asynccontextmanager
async def lifespan(app):
    validate_runtime_profile()
    from core.domain import background_embeddings
    from core.runtime import recover_interrupted
    recover_interrupted()
    from core.domain import library_monitor
    from core.infra.observability import archive
    from core.verify import project_checks
    # Cleanup is registered before each start to cover partial initialization.
    # ExitStack continues all remaining stops even if a stop itself fails.
    with ExitStack() as cleanup:
        cleanup.callback(close_pool)
        cleanup.callback(archive.stop)
        archive.start()
        cleanup.callback(background_embeddings.stop)
        background_embeddings.start()
        cleanup.callback(project_checks.stop)
        cleanup.callback(library_monitor.stop)
        library_monitor.start()
        project_checks.start()
        from core.verify import node_verification
        cleanup.callback(node_verification.stop_auto)
        node_verification.start_auto()
        # Runs may enqueue derived writes until their finalization is complete.
        # LIFO cleanup drains runs, then post-processing, before closing the DB.
        cleanup.callback(postprocess.shutdown)
        postprocess.start()
        cleanup.callback(runtime.shutdown)
        cleanup.callback(notification_worker.stop)
        notification_worker.start()
        yield


app = FastAPI(
    lifespan=lifespan,
    title="Cora API",
    version="0.1.0",
)

app.add_middleware(AuthMiddleware)
app.include_router(auth_router)
app.include_router(update_router)
app.include_router(managed_apps_router)
app.include_router(machines_router)
app.include_router(runtime_router)
app.include_router(orchestration_router)
app.include_router(permissions_router)
app.include_router(monitoring_router)
app.include_router(project_checks_router)
app.include_router(node_verification_router)
app.include_router(roadmap_classifier_router)
app.include_router(files_router)
app.include_router(library_router)
app.include_router(attachments_router)
app.include_router(audio_router)
app.include_router(calendar_router)
app.include_router(notifications_router)
app.include_router(architecture_router)
app.include_router(automation_router)
app.include_router(programmer_router)
# Formerly inline in this file; included here so the route order is unchanged.
app.include_router(system_router)
app.include_router(conversations_router)
app.include_router(memory_router)

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
        from core.shadow_router import primary_route as shadow_primary_route
        primary_route = shadow_primary_route(result["messages"])
        run.timings["primary_route"] = primary_route
        observed_calls = list(run.timings.get('inference_observations', []))
        last_reply = observed_calls[-1] if observed_calls else {}
        assistant_message = save_message(
            conversation_id=thread_id,
            role="assistant",
            content=response,
            agent_id="supervisor",
            model_id=last_reply.get("reported_model"),
            parent_message_id=str(user_message["id"]),
            metadata={"source": "chat_api", "run_id": run.id, "inference_observations": observed_calls,
                      "response_model_source": "provider" if last_reply.get("reported_model") else "unobserved"},
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
        postprocess.submit(_postprocess_turn, thread_id, message, response, str(user_message["id"]), str(assistant_message["id"]), str(run.id), primary_route)
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
    from core.chat_tools import validate_selection
    from tools import supervisor_tools
    try:
        validate_selection(request.manual_tools, supervisor_tools)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    thread_id = str(request.thread_id) if request.thread_id else str(uuid.uuid4())
    if request.attachment_ids:
        attachment_rows(thread_id, request.attachment_ids)
    try:
        return runtime.submit(thread_id, lambda run: execute_chat(request, run).model_dump(), graph_version=architecture_graph()["version"])
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(503, "Runtime non disponibile; verifica Attività e riavvia il backend.") from error


@app.get("/api/v1/chat/tools")
def chat_tools_endpoint():
    from core.chat_tools import chat_tool_options
    return chat_tool_options()


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


postprocess = Postprocessing()


def _postprocess_turn(thread_id,message,response,user_id,assistant_id,run_id="",primary_route="direct"):
    # These are independent derived views: failure in one must not skip the others.
    tasks = (
        ("summary", lambda: schedule_summary(thread_id)),
        ("transcript", lambda: refresh_transcript(thread_id)),
        ("shadow_router", lambda: __import__("core.shadow_router", fromlist=["record_example"]).record_example(
            request_text=message, primary=primary_route, thread_id=thread_id, run_id=run_id,
        )),
        ("episode", lambda: create_episode(
            title=message.replace("\n", " ")[:80] or "Turno chat",
            summary="Richiesta: " + message[:240] + "\nRisultato: " + response[:420],
            conversation_id=thread_id, episode_type="conversation_turn", agent_id="supervisor",
            metadata={"user_message_id":user_id, "assistant_message_id":assistant_id},
        )),
    )
    for action, task in tasks:
        try:
            task()
        except Exception as error:
            # Only the stage and exception class enter best-effort technical telemetry.
            try:
                from core.infra.logging import log_event
                log_event("postprocess_failed", component="postprocess",
                          status="error", data={"action": action, "error_type": type(error).__name__})
            except Exception:
                pass  # Derived work must never invalidate a committed chat response.
