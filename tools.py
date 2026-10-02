import json
import uuid
from collections.abc import Callable

from langchain_core.messages import HumanMessage
from core.governance import agent_tool

from core.component_bus import component_bus
from core.logging import logged_operation, tail_events
from core.memory import delete_memory, save_memory, search_memories
from core.permissions import require_permission
from core.protocol import TaskEnvelope
from core.registry import registry_json
from core.run_lifecycle import RunCancelled, create_run, transition_run
from core.runtime_context import RunTimedOut, bind_runtime, current_runtime
from core.runtime import RunStopped
from core.working_memory import set_working_memory
from local_tools import (
    calculator_tool as _calculator_tool,
    list_project_files as _list_project_files,
    read_project_file as _read_project_file,
    system_status_tool as _system_status_tool,
)


def _require_supervisor_permission(action: str) -> None:
    require_permission("supervisor", action)


@agent_tool("supervisor")
def calculator_tool(expression: str) -> str:
    """Esegue aritmetica di base dopo il controllo permessi del Supervisor."""
    _require_supervisor_permission("calculate")
    return _calculator_tool.invoke({"expression": expression})


@agent_tool("supervisor")
def system_status_tool() -> str:
    """Legge CPU, RAM e disco dopo il controllo permessi del Supervisor."""
    _require_supervisor_permission("inspect_runtime")
    raw = _system_status_tool.invoke({})
    try:
        status = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return str(raw)
    return (
        f"CPU {status['cpu_percent']}% · "
        f"RAM {status['ram_used_gb']} / {status['ram_total_gb']} GB "
        f"({status['ram_percent']}%) · "
        f"Disco {status['disk_used_gb']} / {status['disk_total_gb']} GB "
        f"({status['disk_percent']}%)"
    )


@agent_tool("supervisor")
def list_project_files(
    directory: str = ".",
    extension: str = "",
    recursive: bool = True,
) -> str:
    """Elenca file autorizzati del progetto dopo il controllo permessi."""
    _require_supervisor_permission("list_project_files")
    return _list_project_files.invoke({
        "directory": directory,
        "extension": extension,
        "recursive": recursive,
    })


@agent_tool("supervisor")
def read_project_file(relative_path: str) -> str:
    """Legge un file autorizzato del progetto dopo il controllo permessi."""
    _require_supervisor_permission("read_project_file")
    return _read_project_file.invoke({"relative_path": relative_path})


@agent_tool("supervisor")
def structure_registry_tool(kind: str = "") -> str:
    """
    Restituisce il registro centrale dei componenti di Cora, con capacità e
    disponibilità strutturale. kind può essere: core, agent, tool, interface.
    Lascia vuoto per vedere tutto il registro.
    """
    _require_supervisor_permission("inspect_structure")
    normalized = kind.strip().lower() or None
    allowed = {None, "core", "agent", "tool", "interface"}
    if normalized not in allowed:
        return "Tipo non valido. Usa: core, agent, tool, interface oppure lascia vuoto."
    return registry_json(kind=normalized)


@agent_tool("supervisor")
def recent_system_events_tool(
    limit: int = 20,
    event_type: str = "",
    component: str = "",
) -> str:
    """Legge gli eventi strutturati più recenti del sistema Cora."""
    _require_supervisor_permission("inspect_events")
    events = tail_events(
        limit=max(1, min(limit, 100)),
        event_type=event_type.strip(),
        component=component.strip(),
    )
    return json.dumps(events, ensure_ascii=False, indent=2)


@agent_tool("supervisor")
def remember_tool(
    memory_type: str,
    key: str,
    content: str,
    importance: int = 3,
    expires_at: str = "",
    reason: str = "",
) -> str:
    """Salva o aggiorna una memoria semantica persistente."""
    _require_supervisor_permission("remember_memory")
    result = save_memory(
        memory_type=memory_type,
        key=key,
        content=content,
        importance=importance,
        expires_at=expires_at.strip() or None,
        source="assistant_selected",
        metadata={"reason": reason.strip()} if reason.strip() else {},
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@agent_tool("supervisor")
def recall_memory_tool(
    query: str = "",
    memory_type: str = "",
    limit: int = 10,
) -> str:
    """Cerca nella memoria persistente locale di Cora."""
    _require_supervisor_permission("recall_memory")
    results = search_memories(
        query=query,
        memory_type=memory_type,
        limit=max(1, min(limit, 50)),
    )
    return json.dumps(results, ensure_ascii=False, indent=2)


@agent_tool("supervisor")
def forget_memory_tool(memory_id: str) -> str:
    """Elimina una singola memoria persistente per ID su richiesta esplicita."""
    _require_supervisor_permission("forget_memory")
    deleted = delete_memory(memory_id)
    return json.dumps(
        {"memory_id": memory_id, "deleted": deleted},
        ensure_ascii=False,
        indent=2,
    )


def _delegate_agent(
    *,
    target: str,
    capability: str,
    query: str,
    thread_id: str,
    graph_loader: Callable[[], object],
):
    parent_run_id, parent_thread_id = current_runtime()
    effective_thread_id = thread_id or parent_thread_id or f"{target}_{uuid.uuid4()}"

    child = create_run(
        thread_id=effective_thread_id,
        kind="component",
        target=target,
        parent_run_id=parent_run_id or None,
        metadata={"capability": capability, "source": "supervisor"},
    )
    child_run_id = str(child["id"])
    from core.runtime import current_run
    parent_runtime = current_run.get()
    if parent_runtime: parent_runtime.component_threads.add(effective_thread_id)
    transition_run(child_run_id, "running")

    envelope = TaskEnvelope(
        run_id=child_run_id,
        thread_id=effective_thread_id,
        source="supervisor",
        target=target,
        capability=capability,
        payload={"query": query},
        context_refs=[parent_run_id] if parent_run_id else [],
    )

    set_working_memory(
        agent_id=target,
        thread_id=effective_thread_id,
        state={
            "status": "running",
            "current_request": query,
            "run_id": child_run_id,
        },
    )

    def handler(task: TaskEnvelope) -> str:
        app = graph_loader()
        state = {"messages": [HumanMessage(content=str(task.payload["query"]))]}
        with bind_runtime(task.run_id, task.thread_id):
            result = app.invoke(state)
        return str(result["messages"][-1].content)

    try:
        with logged_operation(
            "agent_delegation",
            component=target,
            thread_id=effective_thread_id,
            data={"query_chars": len(query), "run_id": child_run_id},
        ):
            result = component_bus.dispatch(envelope, handler)
        transition_run(child_run_id, "completed")
        set_working_memory(
            agent_id=target,
            thread_id=effective_thread_id,
            state={
                "status": "completed",
                "current_request": query,
                "last_response": result.content[:1200],
                "run_id": child_run_id,
            },
        )
        return result.content
    except BaseException as error:
        terminal_status = (
            "cancelled" if isinstance(error, RunCancelled) or (isinstance(error,RunStopped) and parent_runtime and parent_runtime.reason == "cancelled")
            else "timed_out" if isinstance(error, RunTimedOut) or (isinstance(error,RunStopped) and parent_runtime and parent_runtime.reason == "timed_out")
            else "failed"
        )
        try:
            transition_run(child_run_id, terminal_status, error_type=type(error).__name__)
        except Exception:
            pass
        set_working_memory(
            agent_id=target,
            thread_id=effective_thread_id,
            state={
                "status": "error",
                "current_request": query,
                "error": str(error)[:1200],
                "run_id": child_run_id,
            },
        )
        raise


@agent_tool("supervisor")
def structure_agent_tool(query: str, thread_id: str = "") -> str:
    """Delega planning, evaluation, control e management allo Structure Agent."""
    _require_supervisor_permission("delegate_structure")

    def load():
        from structure_agent.structure_graph import graph
        return graph

    return _delegate_agent(
        target="structure_agent",
        capability="structure",
        query=query,
        thread_id=thread_id,
        graph_loader=load,
    )


@agent_tool("supervisor")
def search_agent_tool(query: str, thread_id: str = "") -> str:
    """Delega ricerca e analisi dei documenti locali al Local Research Agent."""
    _require_supervisor_permission("delegate_research")

    def load():
        from search_agent.search_graph import graph
        return graph

    return _delegate_agent(
        target="local_research_agent",
        capability="document_research",
        query=query,
        thread_id=thread_id,
        graph_loader=load,
    )


@agent_tool("supervisor")
def audio_agent_tool(query: str, thread_id: str = "") -> str:
    """Delega trascrizione e analisi audio all'Audio Agent."""
    _require_supervisor_permission("delegate_audio")

    def load():
        from audio_agent.audio_graph import graph
        return graph

    return _delegate_agent(
        target="audio_agent",
        capability="audio",
        query=query,
        thread_id=thread_id,
        graph_loader=load,
    )


@agent_tool("supervisor")
def email_agent_tool(query: str, thread_id: str = "") -> str:
    """Delega ricerca mail, bozze e preventivi all'Email & Quotes Agent."""
    _require_supervisor_permission("delegate_email")

    def load():
        from email_agent.email_graph import graph
        return graph

    return _delegate_agent(
        target="email_quotes_agent",
        capability="email_quotes",
        query=query,
        thread_id=thread_id,
        graph_loader=load,
    )


supervisor_tools = [
    calculator_tool,
    system_status_tool,
    list_project_files,
    read_project_file,
    structure_registry_tool,
    recent_system_events_tool,
    recall_memory_tool,
    remember_tool,
    forget_memory_tool,
    structure_agent_tool,
    search_agent_tool,
    audio_agent_tool,
    email_agent_tool,
]


from core.calendar_tools import calendar_tools_for
supervisor_tools += calendar_tools_for("supervisor")
