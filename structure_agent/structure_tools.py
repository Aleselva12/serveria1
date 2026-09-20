from __future__ import annotations

import json

from langchain_core.tools import tool

from core.logging import tail_events
from core.memory import memory_stats
from core.registry import get_registry
from local_tools import list_project_files, read_project_file, system_status_tool


@tool
def structure_components(kind: str = "") -> str:
    """
    Restituisce il registro centrale dei componenti di Cora.
    kind può essere core, agent, tool, interface oppure vuoto.
    """
    normalized = kind.strip().lower() or None
    allowed = {None, "core", "agent", "tool", "interface"}
    if normalized not in allowed:
        return "Tipo non valido. Usa: core, agent, tool, interface oppure lascia vuoto."
    return json.dumps(get_registry(kind=normalized), ensure_ascii=False, indent=2)


@tool
def structure_memory_status() -> str:
    """Restituisce solo statistiche tecniche della memoria persistente."""
    return json.dumps(memory_stats(), ensure_ascii=False, indent=2)


@tool
def structure_recent_events(
    limit: int = 30,
    event_type: str = "",
    component: str = "",
) -> str:
    """Legge eventi recenti del log strutturato per diagnosi."""
    events = tail_events(
        limit=max(1, min(limit, 100)),
        event_type=event_type.strip(),
        component=component.strip(),
    )
    return json.dumps(events, ensure_ascii=False, indent=2)


@tool
def structure_control_snapshot(event_limit: int = 20) -> str:
    """
    Restituisce una fotografia tecnica sintetica utile a control e management:
    componenti dichiarati, stato sistema, memoria e ultimi eventi strutturati.
    Non modifica nulla.
    """
    snapshot = {
        "registry": get_registry(),
        "system_status": system_status_tool.invoke({}),
        "memory": memory_stats(),
        "recent_events": tail_events(limit=max(1, min(event_limit, 50))),
    }
    return json.dumps(snapshot, ensure_ascii=False, indent=2)


STRUCTURE_TOOLS = [
    structure_components,
    system_status_tool,
    structure_memory_status,
    structure_recent_events,
    structure_control_snapshot,
    list_project_files,
    read_project_file,
]
