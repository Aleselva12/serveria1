import json
import uuid
from collections.abc import Callable

from langchain_core.messages import HumanMessage
from core.governance import agent_tool

from core.component_bus import component_bus
from core.logging import logged_operation, tail_events
from core.memory import delete_memory, save_memory, search_memories
from core.system_context import get_system_context
from core.permissions import require_permission
from core.protocol import TaskEnvelope
from core.registry import registry_json
from core.run_lifecycle import RunCancelled, create_run, transition_run
from core.runtime_context import RunTimedOut, bind_runtime, current_runtime
from core.runtime import RunStopped, checkpoint, publish_text
from core.run_states import DurabilityLost
from core.working_memory import set_working_memory
from local_tools import (
    calculator_tool as _calculator_tool,
    list_project_files as _list_project_files,
    read_project_file as _read_project_file,
    system_status_tool as _system_status_tool,
)


def _require_supervisor_permission(action: str) -> None:
    require_permission("supervisor", action)


@agent_tool('supervisor', capability='calculator_tool', actions=('calculate',), effect='compute', retry='safe', response_mode='final')
def calculator_tool(expression: str) -> str:
    """Esegue aritmetica di base dopo il controllo permessi del Supervisor."""
    _require_supervisor_permission("calculate")
    return _calculator_tool.invoke({"expression": expression})


@agent_tool('supervisor', capability='system_status_tool', actions=('inspect_runtime',), effect='read', retry='safe', response_mode='final')
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


@agent_tool('supervisor', capability='list_project_files', actions=('list_project_files',), effect='read', retry='safe')
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


@agent_tool('supervisor', capability='read_project_file', actions=('read_project_file',), effect='read', retry='safe')
def read_project_file(relative_path: str) -> str:
    """Legge un file autorizzato del progetto dopo il controllo permessi."""
    _require_supervisor_permission("read_project_file")
    return _read_project_file.invoke({"relative_path": relative_path})


@agent_tool('supervisor', capability='structure_registry_tool', actions=('inspect_structure',), effect='read', retry='safe')
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


@agent_tool('supervisor', capability='recent_system_events_tool', actions=('inspect_events',), effect='read', retry='safe')
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


@agent_tool('supervisor', capability='owner_context_tool', actions=('inspect_owner',), effect='read', retry='safe')
def owner_context_tool() -> str:
    """Carica su richiesta il contesto persistente mantenuto esplicitamente dal proprietario."""
    _require_supervisor_permission("inspect_owner")
    context = get_system_context()
    return json.dumps(
        {
            "version": context.get("version"),
            "content": context.get("content") or "",
            "updated_at": context.get("updated_at"),
        },
        ensure_ascii=False,
        default=str,
    )


@agent_tool('supervisor', capability='remember_tool', actions=('remember_memory',), effect='write', retry='never', version=2)
def remember_tool(
    memory_type: str,
    key: str,
    content: str,
    importance: int = 3,
    expires_at: str = "",
    reason: str = "",
    assertion: str = "inference",
    confidence: float | None = None,
    expected_version: int = 0,
    expected_memory_id: str = "",
) -> str:
    """Annota memoria: user_statement, observation o inference. Per aggiornare leggi ID e versione con recall_memory_tool e passa expected_memory_id e expected_version; 0 crea. Correggere memorie dell'utente richiede approvazione."""
    _require_supervisor_permission("remember_memory")
    result = save_memory(
        memory_type=memory_type,
        key=key,
        content=content,
        importance=importance,
        expires_at=expires_at.strip() or None,
        source="assistant_selected",
        metadata={"reason": reason.strip()},
        assertion=assertion,
        confidence=confidence,
        expected_version=expected_version,
        expected_memory_id=expected_memory_id or None,
        editor="agent",
        thread_id=current_runtime()[1] or None,
        source_ref=current_runtime()[0] or None,
    )
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


@agent_tool('supervisor', capability='recall_memory_tool', actions=('recall_memory',), effect='read', retry='safe')
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
    return json.dumps(results, ensure_ascii=False, indent=2, default=str)


@agent_tool('supervisor', capability='forget_memory_tool', actions=('forget_memory',), effect='write', retry='never', version=2)
def forget_memory_tool(memory_id: str, expected_version: int) -> str:
    """Elimina una memoria su richiesta esplicita, indicando la versione letta. Le memorie dell'utente richiedono approvazione."""
    _require_supervisor_permission("forget_memory")
    deleted = delete_memory(memory_id,editor="agent",expected_version=expected_version)
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
    approval_offset = len(parent_runtime.approvals) if parent_runtime else 0

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
            result = None
            for mode, chunk in app.stream(state, stream_mode=["messages", "values"]):
                checkpoint()
                if mode == "values": result = chunk
                elif mode == "messages" and parent_runtime:
                    message, metadata = chunk
                    if metadata.get("langgraph_node") == "call_llm":
                        role = metadata.get("cora_role", target)
                        span = (task.run_id, role, message.id, metadata.get("langgraph_step"))
                        publish_text(parent_runtime, role, span, message.content)
            if not result: raise RuntimeError("Grafo delegato senza risultato.")
        return str(result["messages"][-1].content)

    try:
        with logged_operation(
            "agent_delegation",
            component=target,
            thread_id=effective_thread_id,
            data={"query_chars": len(query), "run_id": child_run_id},
        ):
            result = component_bus.dispatch(envelope, handler)
        child_approvals = parent_runtime.approvals[approval_offset:] if parent_runtime else []
        if child_approvals: result = result.model_copy(update={"status":"waiting_approval"})
        child_status = "awaiting_approval" if child_approvals else "completed"
        transition_run(child_run_id,child_status,result=result.model_dump(mode="json"),approval_ids=child_approvals)
        set_working_memory(
            agent_id=target,
            thread_id=effective_thread_id,
            state={
                "status": child_status,
                "current_request": query,
                "last_response": result.content[:1200],
                "run_id": child_run_id,
            },
        )
        return result.content
    except BaseException as error:
        terminal_status = (
            "cancelled" if isinstance(error, RunCancelled) or (isinstance(error,RunStopped) and error.reason == "cancelled")
            else "timed_out" if isinstance(error, RunTimedOut) or (isinstance(error,RunStopped) and error.reason == "timed_out")
            else "failed"
        )
        try:
            if terminal_status in {"cancelled","timed_out"}: transition_run(child_run_id,"cancelling")
            transition_run(child_run_id, terminal_status, error_type=type(error).__name__)
        except Exception as persistence_error:
            raise DurabilityLost("ChildRunStateNotPersisted") from persistence_error
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


@agent_tool('supervisor', capability='structure_agent_tool', actions=('delegate_structure',), effect='delegate', retry='never', response_mode='final')
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


@agent_tool('supervisor', capability='search_agent_tool', actions=('delegate_research',), effect='delegate', retry='never', response_mode='final')
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


@agent_tool('supervisor', capability='audio_agent_tool', actions=('delegate_audio',), effect='delegate', retry='never', response_mode='final')
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


@agent_tool('supervisor', capability='email_agent_tool', actions=('delegate_email',), effect='delegate', retry='never', response_mode='final')
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


@agent_tool('supervisor', capability='programmer_agent_tool', actions=('delegate_programmer',), effect='delegate', retry='never', response_mode='final')
def programmer_agent_tool(query: str, workspace_id: str) -> str:
    """Delega creazione di tool/automazioni al Programmatore. Richiede l'ID di un workspace già creato nella pagina Programma."""
    _require_supervisor_permission("delegate_programmer")
    from programmer_agent.workspace import bind_workspace

    def load():
        from programmer_agent.programmer_graph import graph
        return graph

    with bind_workspace(workspace_id):
        return _delegate_agent(target="programmer_agent", capability="programming", query=query,
                               thread_id=workspace_id, graph_loader=load)


supervisor_tools = [
    calculator_tool,
    system_status_tool,
    list_project_files,
    read_project_file,
    structure_registry_tool,
    recent_system_events_tool,
    owner_context_tool,
    recall_memory_tool,
    remember_tool,
    forget_memory_tool,
    structure_agent_tool,
    search_agent_tool,
    audio_agent_tool,
    email_agent_tool,
    programmer_agent_tool,
]


from core.calendar_tools import calendar_tools_for
supervisor_tools += calendar_tools_for("supervisor")


@agent_tool('supervisor', capability='library_list', actions=('library_read',), effect='read', retry='safe')
def library_list(directory: str = ".", recursive: bool = True) -> str:
    """Elenca documenti nella sola Libreria IA, per scoprire i percorsi da leggere."""
    from search_agent.search_tools import list_local_documents
    return list_local_documents.invoke({"directory": directory, "recursive": recursive})


@agent_tool('supervisor', capability='library_search', actions=('library_read',), effect='read', retry='safe')
def library_search(query: str, directory: str = ".", max_results: int = 10) -> str:
    """Cerca parole nei nomi e nei contenuti testuali/PDF/Word della sola Libreria IA."""
    from search_agent.search_tools import search_local_documents
    return search_local_documents.invoke({"query": query, "directory": directory, "max_results": max_results})


@agent_tool('supervisor', capability='library_read', actions=('library_read',), effect='read', retry='safe')
def library_read(relative_path: str) -> str:
    """Legge un documento della sola Libreria IA usando il percorso relativo trovato."""
    from search_agent.search_tools import read_local_document
    return read_local_document.invoke({"relative_path": relative_path})


supervisor_tools += [library_list, library_search, library_read]
