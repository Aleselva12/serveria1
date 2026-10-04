from __future__ import annotations
import json
from core.governance import agent_tool, capability_registry
from core.runtime import checkpoint
from programmer_agent import workspace as ws
from programmer_agent import knowledge
from programmer_agent.checks import run_check

ACTOR = "programmer_agent"


def _workspace(workspace_id: str) -> str:
    from uuid import UUID
    identifier = str(UUID(workspace_id))
    selected = ws.CURRENT.get()
    if selected and identifier != selected:
        raise ValueError("La capability deve usare il workspace selezionato per questo run.")
    ws.directory(identifier)
    return identifier


@agent_tool(ACTOR, actions=('read_workspace',), effect='read', retry='safe')
def programmer_list_files(workspace_id: str, query: str = "", limit: int = 100) -> dict:
    """Elenca file dello snapshot selezionato; query filtra i percorsi. Nessun dato privato del server."""
    paths = [p for p in ws.list_files(_workspace(workspace_id)) if query.lower() in p.lower()]
    limit = max(1, min(200, limit))
    return {"files": paths[:limit], "total": len(paths), "truncated": len(paths) > limit}


@agent_tool(ACTOR, actions=('read_workspace',), effect='read', retry='safe')
def programmer_read_file(workspace_id: str, path: str, start_line: int = 1, line_count: int = 120) -> dict:
    """Legge righe di un file del workspace, restituendo sha256 per una successiva scrittura."""
    return ws.read(_workspace(workspace_id), path, start_line, line_count)


@agent_tool(ACTOR, actions=('read_workspace',), effect='read', retry='safe')
def programmer_search_code(workspace_id: str, query: str, limit: int = 30) -> dict:
    """Ricerca lessicale senza regex nel codice dello snapshot. Restituisce percorso e riga."""
    if not query.strip():
        raise ValueError("Query vuota.")
    limit = max(1, min(50, limit))
    matches = []
    for path in ws.list_files(_workspace(workspace_id)):
        checkpoint()
        text = ws.file_path(_workspace(workspace_id), path).read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if query.lower() in line.lower():
                matches.append({"path": path, "line": number, "text": line[:300]})
                if len(matches) == limit:
                    return {"matches": matches, "truncated": True}
    return {"matches": matches, "truncated": False}


@agent_tool(ACTOR, actions=('write_workspace',), effect='write', retry='never')
def programmer_write_file(workspace_id: str, path: str, content: str, expected_sha256: str = "") -> dict:
    """Scrive soltanto nel workspace: hash letto per aggiornare, hash vuoto per creare. Mai codice attivo."""
    return ws.write(_workspace(workspace_id), path, content, expected_sha256)


@agent_tool(ACTOR, actions=('read_workspace',), effect='read', retry='safe')
def programmer_diff(workspace_id: str) -> dict:
    """Confronta il workspace con lo snapshot iniziale; nessuna applicazione al programma attivo."""
    return ws.diff(_workspace(workspace_id))


@agent_tool(ACTOR, actions=('inspect_catalog',), effect='read', retry='safe')
def programmer_catalog(workspace_id: str, query: str = "", limit: int = 15) -> dict:
    """Cerca contratti eseguibili reali: ID, input/output, permessi e collegamento agli agenti."""
    _workspace(workspace_id)
    tools = capability_registry()["tools"]
    matches = [t for t in tools if query.lower() in (t["id"] + " " + t["description"]).lower()]
    limit = max(1, min(25, limit))
    fields = ("id", "version", "description", "input_schema", "native_output_schema", "required_actions", "effect", "connected")
    return {"tools": [{k: t[k] for k in fields} for t in matches[:limit]], "total": len(matches), "truncated": len(matches) > limit}


@agent_tool(ACTOR, actions=('read_skills',), effect='read', retry='safe')
def programmer_read_skill(workspace_id: str, name: str) -> str:
    """Carica su richiesta una skill: create-cora-tool, create-cora-automation, verify-component, understand-project."""
    _workspace(workspace_id)
    return knowledge.read_skill(name)


@agent_tool(ACTOR, actions=('read_skills',), effect='read', retry='safe')
def programmer_template(workspace_id: str, name: str) -> str:
    """Legge un modello pronto: tool, tool_test o automation. Adattalo alla richiesta prima di salvarlo."""
    _workspace(workspace_id)
    return knowledge.template(name)


@agent_tool(ACTOR, actions=('check_workspace',), conditional_actions=('execute_checks',), effect='write', retry='never')
def programmer_check(workspace_id: str, profile: str = "syntax") -> dict:
    """Verifica syntax (senza esecuzione) o python_tests (solo Docker isolato); salva il rapporto nel workspace."""
    if profile == "python_tests":
        from core.permissions import require_permission
        require_permission(ACTOR, "execute_checks")
    return run_check(_workspace(workspace_id), profile)


@agent_tool(ACTOR, actions=('read_workspace',), effect='read', retry='safe')
def programmer_graph(workspace_id: str, query: str, node_id: str = "") -> dict:
    """Consulta il grafo Graphify importato nello snapshot; segnala assenza o modifiche successive."""
    return knowledge.query_graph(_workspace(workspace_id), query, node_id)


@agent_tool(ACTOR, actions=('inspect_catalog',), effect='compute', retry='safe')
def programmer_validate_automation(workspace_id: str, data: dict) -> dict:
    """Valida una bozza usando lo stesso schema dell'editor Tools. Non la attiva o esegue."""
    _workspace(workspace_id)
    from core.automation_drafts import validate_graph
    from core.tool_inventory import inventory
    ids = {e["id"] for e in inventory()["entries"] if e["kind"] == "tool"}
    return {"draft": validate_graph(data, tool_ids=ids), "executes_actions": False}


PROGRAMMER_TOOLS = [
    programmer_list_files, programmer_read_file, programmer_search_code,
    programmer_write_file, programmer_diff, programmer_catalog,
    programmer_read_skill, programmer_template, programmer_check,
    programmer_graph, programmer_validate_automation,
]
