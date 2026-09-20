import json
import uuid

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from core.logging import logged_operation, tail_events
from core.memory import delete_memory, save_memory, search_memories
from core.registry import registry_json
from local_tools import (
    calculator_tool,
    list_project_files,
    read_project_file,
    system_status_tool,
)


@tool
def structure_registry_tool(kind: str = "") -> str:
    """
    Restituisce il registro centrale dei componenti di Cora, con capacità e
    disponibilità strutturale. kind può essere: core, agent, tool, interface.
    Lascia vuoto per vedere tutto il registro.
    """
    normalized = kind.strip().lower() or None
    allowed = {None, "core", "agent", "tool", "interface"}
    if normalized not in allowed:
        return "Tipo non valido. Usa: core, agent, tool, interface oppure lascia vuoto."
    return registry_json(kind=normalized)


@tool
def recent_system_events_tool(
    limit: int = 20,
    event_type: str = "",
    component: str = "",
) -> str:
    """
    Legge gli eventi strutturati più recenti del sistema Cora.
    È uno strumento di osservazione: non modifica log o memoria.
    """
    events = tail_events(
        limit=max(1, min(limit, 100)),
        event_type=event_type.strip(),
        component=component.strip(),
    )
    return json.dumps(events, ensure_ascii=False, indent=2)


@tool
def remember_tool(
    memory_type: str,
    key: str,
    content: str,
    importance: int = 3,
    expires_at: str = "",
) -> str:
    """
    Salva o aggiorna una memoria persistente locale.
    Usare solo quando l'utente chiede esplicitamente di ricordare/conservare
    un'informazione o quando il flusso applicativo lo autorizza esplicitamente.
    """
    result = save_memory(
        memory_type=memory_type,
        key=key,
        content=content,
        importance=importance,
        expires_at=expires_at.strip() or None,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def recall_memory_tool(
    query: str = "",
    memory_type: str = "",
    limit: int = 10,
) -> str:
    """
    Cerca nella memoria persistente locale di Cora.
    Usa una ricerca lessicale semplice su chiave e contenuto.
    """
    results = search_memories(
        query=query,
        memory_type=memory_type,
        limit=max(1, min(limit, 50)),
    )
    return json.dumps(results, ensure_ascii=False, indent=2)


@tool
def forget_memory_tool(memory_id: str) -> str:
    """
    Elimina una singola memoria persistente per ID.
    Usare solo quando l'utente chiede esplicitamente di cancellarla.
    """
    deleted = delete_memory(memory_id)
    return json.dumps(
        {"memory_id": memory_id, "deleted": deleted},
        ensure_ascii=False,
        indent=2,
    )


@tool
def structure_agent_tool(query: str, thread_id: str = "") -> str:
    """
    Usa lo Structure Agent per analizzare architettura, componenti, dipendenze,
    stato runtime, log recenti e possibili problemi strutturali di Cora.
    È read-only e non modifica file, configurazione o memoria.
    """
    from structure_agent.structure_graph import graph as structure_app

    effective_thread_id = thread_id or f"structure_{uuid.uuid4()}"
    config = {"configurable": {"thread_id": effective_thread_id}}
    state = {"messages": [HumanMessage(content=query)]}

    with logged_operation(
        "agent_delegation",
        component="structure_agent",
        thread_id=effective_thread_id,
        data={"query_chars": len(query)},
    ):
        result = structure_app.invoke(state, config=config)

    return result["messages"][-1].content


@tool
def search_agent_tool(query: str, thread_id: str = "") -> str:
    """
    Usa il Local Research Agent per trovare, leggere, confrontare e analizzare
    informazioni contenute nei documenti locali autorizzati. Non usa Internet.
    """
    from search_agent.search_graph import create_search_graph

    search_app = create_search_graph()
    effective_thread_id = thread_id or f"search_{uuid.uuid4()}"
    config = {"configurable": {"thread_id": effective_thread_id}}
    state = {"messages": [HumanMessage(content=query)]}

    with logged_operation(
        "agent_delegation",
        component="local_research_agent",
        thread_id=effective_thread_id,
        data={"query_chars": len(query)},
    ):
        result = search_app.invoke(state, config=config)

    return result["messages"][-1].content


@tool
def audio_agent_tool(query: str, thread_id: str = "") -> str:
    """
    Usa l'Audio Agent per trovare e trascrivere file audio locali e,
    quando richiesto, riassumere o analizzare la trascrizione.
    """
    from audio_agent.audio_graph import graph as audio_app

    effective_thread_id = thread_id or f"audio_{uuid.uuid4()}"
    config = {"configurable": {"thread_id": effective_thread_id}}
    state = {"messages": [HumanMessage(content=query)]}

    with logged_operation(
        "agent_delegation",
        component="audio_agent",
        thread_id=effective_thread_id,
        data={"query_chars": len(query)},
    ):
        result = audio_app.invoke(state, config=config)

    return result["messages"][-1].content


@tool
def email_agent_tool(query: str, thread_id: str = "") -> str:
    """
    Usa l'Email & Quotes Agent per cercare nell'archivio mail, riassumere
    la posta di una giornata, preparare bozze e generare preventivi PDF.
    """
    from email_agent.email_graph import graph as email_app

    effective_thread_id = thread_id or f"email_{uuid.uuid4()}"
    config = {"configurable": {"thread_id": effective_thread_id}}
    state = {"messages": [HumanMessage(content=query)]}

    with logged_operation(
        "agent_delegation",
        component="email_quotes_agent",
        thread_id=effective_thread_id,
        data={"query_chars": len(query)},
    ):
        result = email_app.invoke(state, config=config)

    return result["messages"][-1].content


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
