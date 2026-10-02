"""Read-only topology extracted from the executable compiled LangGraphs."""
import hashlib
import importlib
import json
from functools import lru_cache
from fastapi import APIRouter, HTTPException, Query
from core.execution_traces import read_runs

router = APIRouter(prefix="/api/v1", tags=["Architecture"])
GRAPH_SOURCES = (
    ("supervisor", "graph", "graph"),
    ("structure_agent", "structure_agent.structure_graph", "graph"),
    ("local_research_agent", "search_agent.search_graph", "create_search_graph"),
    ("audio_agent", "audio_agent.audio_graph", "graph"),
    ("email_quotes_agent", "email_agent.email_graph", "graph"),
)


@lru_cache(maxsize=1)
def architecture_graph():
    graphs, errors = [], []
    for component, module, attribute in GRAPH_SOURCES:
        try:
            compiled = getattr(importlib.import_module(module), attribute)
            if attribute.startswith("create_"):
                compiled = compiled()
            topology = compiled.get_graph()
            graphs.append(dict(id=component,
                               nodes=[dict(id=str(n.id), name=n.name) for n in topology.nodes.values()],
                               edges=[dict(source=str(e.source), target=str(e.target),
                                           conditional=bool(e.conditional), label=str(e.data or "")) for e in topology.edges]))
        except Exception as error:
            errors.append(dict(component=component, error_type=type(error).__name__))
    # Delegation edges are derived from tools bound to the supervisor.
    from tools import supervisor_tools
    targets = {"structure_agent_tool": "structure_agent", "search_agent_tool": "local_research_agent",
               "audio_agent_tool": "audio_agent", "email_agent_tool": "email_quotes_agent"}
    delegations = [dict(source="supervisor", target=targets[t.name], tool=t.name)
                   for t in supervisor_tools if t.name in targets]
    payload = dict(graphs=graphs, delegations=delegations, errors=errors)
    version = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    return dict(version=version, **payload)


@router.get("/architecture/graph")
def graph_endpoint():
    return architecture_graph()


@router.get("/runs")
def runs(limit: int = Query(50, ge=1, le=100)):
    return read_runs(limit)


@router.get("/runs/{run_id}")
def run_detail(run_id: str):
    matches = read_runs(run_id=run_id)
    if not matches:
        raise HTTPException(404, "Esecuzione non trovata")
    return matches[0]


@lru_cache(maxsize=1)
def architecture_overview():
    """System-level view: agent delegation, shared support and direct API paths."""
    from core.registry import get_registry
    from core.models import get_model_name
    from tools import supervisor_tools
    from core.calendar_api import router as calendar_router
    from core.monitoring import router as monitoring_router
    from core.server_files import router as files_router
    from core.ia_library import router as library_router

    registry = get_registry()
    roles = {"supervisor": "supervisor", "structure_agent": "structure",
             "local_research_agent": "research", "audio_agent": "audio",
             "email_quotes_agent": "email"}
    nodes = [{**c, "kind": "agent" if c["id"] in roles else c["kind"],
              "model": get_model_name(roles[c["id"]]) if c["id"] in roles else None}
             for c in registry["components"] if c["id"] in roles or c["kind"] == "interface"]
    targets = {"structure_agent_tool": "structure_agent", "search_agent_tool": "local_research_agent",
               "audio_agent_tool": "audio_agent", "email_agent_tool": "email_quotes_agent"}
    edges = [dict(source="react_ui", target="fastapi_backend", label="Richiesta chat", kind="request"),
             dict(source="fastapi_backend", target="supervisor", label="/chat", kind="request")]
    edges += [dict(source="supervisor", target=targets[t.name], label="Delega", kind="delegation")
              for t in supervisor_tools if t.name in targets]
    components = [c for c in registry["components"] if c["kind"] == "core" and c["id"] != "supervisor"]
    direct_paths = []
    for identifier, name, trigger, router, description in (
        ("calendar_direct", "Calendario", "Azioni dell’utente", calendar_router,
         "Eventi, storico e approvazione delle proposte attraverso API e PostgreSQL."),
        ("files_direct", "File server", "Azioni dell’utente", files_router,
         "Esplorazione, caricamento e gestione dei file tramite API."),
        ("library_direct", "Libreria IA", "Azioni dell’utente", library_router,
         "Gestione delle copie dei file tramite API."),
        ("monitoring_direct", "Monitoraggio", "Aggiornamento della Home", monitoring_router,
         "Lettura di sensori e stato dei servizi con codice deterministico."),
    ):
        paths = sorted({r.path for r in router.routes})
        if paths:
            direct_paths.append(dict(id=identifier, name=name, trigger=trigger,
                                     description=description, routes=paths, source=router.routes[0].endpoint.__module__))
    # These hooks are executed by /chat itself, outside the agent graph.
    automations = [dict(id="chat_persistence", name="Salvataggio della chat",
                        trigger="Richiesta e risposta chat", source="api.py:chat",
                        description="Cronologia, stato temporaneo ed episodio salvati da codice deterministico. Nessun agente aggiuntivo.")]
    payload = dict(nodes=nodes, edges=edges, components=components, direct_paths=direct_paths,
                   automations=automations, framework="LangGraph")
    version = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    return dict(version=version, **payload)


@router.get("/architecture/overview")
def overview_endpoint():
    return architecture_overview()
