"""Agent catalog and owner model assignment; legacy topology remains read-only."""
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
    ("programmer_agent", "programmer_agent.programmer_graph", "graph"),
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
               "audio_agent_tool": "audio_agent", "email_agent_tool": "email_quotes_agent", "programmer_agent_tool": "programmer_agent"}
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
    return read_runs(limit,include_events=False)


@router.get("/runs/{run_id}")
def run_detail(run_id: str):
    try: matches = read_runs(run_id=run_id)
    except (ValueError,KeyError) as error: raise HTTPException(404,'Esecuzione non trovata') from error
    if not matches:
        raise HTTPException(404, "Esecuzione non trovata")
    return matches[0]


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
             "email_quotes_agent": "email", "programmer_agent": "programmer"}
    nodes = [{**c, "kind": "agent" if c["id"] in roles else c["kind"],
              "model": get_model_name(roles[c["id"]]) if c["id"] in roles else None}
             for c in registry["components"] if c["id"] in roles or c["kind"] == "interface"]
    targets = {"structure_agent_tool": "structure_agent", "search_agent_tool": "local_research_agent",
               "audio_agent_tool": "audio_agent", "email_agent_tool": "email_quotes_agent", "programmer_agent_tool": "programmer_agent"}
    edges = [dict(source="react_ui", target="fastapi_backend", label="Richiesta chat", kind="request"),
             dict(source="fastapi_backend", target="supervisor", label="/chat", kind="request")]
    edges += [dict(source="supervisor", target=targets[t.name], label="Delega", kind="delegation")
              for t in supervisor_tools if t.name in targets]
    edges.append(dict(source="fastapi_backend", target="programmer_agent", label="Copilot /programmer/runs", kind="request"))
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


@router.get('/architecture/agents')
def agents_catalog():
    from core.agent_models import ROLES, bindings
    from core.registry import get_registry
    from core.models import get_model_name
    from core.tool_inventory import inventory, SOURCES
    from core.runtime_status import component_runtime_status
    from core.machines_api import _read
    configured = bindings()
    machines = {m['id']: m['name'] for m in _read()}
    owners = dict(zip(('supervisor', 'programmer_agent', 'structure_agent', 'local_research_agent', 'audio_agent', 'email_quotes_agent'),
                      (row[3] for row in SOURCES)))
    tools = inventory()
    runtime = component_runtime_status()['components']
    registry = get_registry()
    agents = []
    for component in registry['components']:
        identifier = component['id']
        if identifier not in ROLES:
            continue
        assignment = configured.get(ROLES[identifier])
        machine = assignment['machine_id'] if assignment else 'local'
        agents.append({**component, 'role': ROLES[identifier], 'model': get_model_name(ROLES[identifier]),
                       'assignment': assignment, 'machine_name': 'Ollama di Cora' if machine == 'local' else machines.get(machine, 'Worker non registrato'),
                       'runtime': runtime.get(identifier, {'status': 'unknown', 'checks': {}}),
                       'tools': [e for e in tools['entries'] if e['kind'] == 'tool' and owners[identifier] in e['agents']]})
    return {'agents': agents, 'components': [c for c in registry['components'] if c['kind'] == 'core' and c['id'] not in ROLES],
            'inventory_errors': tools['errors']}


@router.get('/architecture/model-targets')
def model_targets():
    from core.machines_api import _read, _settings
    return {'targets': [dict(id='local', name='Ollama di Cora', enabled=True, active_model=None)] + [
        dict(id=m['id'], name=m['name'], enabled=_settings(m)['enabled'],
             active_model=_settings(m)['profiles'][_settings(m)['active_profile']]) for m in _read()]}


@router.get('/architecture/model-targets/{machine_id}')
def target_models(machine_id: str):
    from core.models import list_ollama_models
    from core.machines_api import _find, _worker_call, _settings
    if machine_id == 'local':
        try:
            return {'models': list_ollama_models(), 'enabled': True, 'active_model': None, 'agent_chat': True}
        except (OSError, ValueError) as error:
            raise HTTPException(503, 'Ollama di Cora non raggiungibile.') from error
    machine = _find(machine_id)
    result = _worker_call(machine, '/models')
    settings = _settings(machine)
    active_model = settings['profiles'][settings['active_profile']]
    # Only the manually active worker profile can be used by agents.
    return {'models': [dict(name=m['name']) for m in result.get('models', []) if m.get('name') == active_model],
            'enabled': settings['enabled'], 'active_model': active_model, 'agent_chat': result.get('agent_chat') is True}


from pydantic import BaseModel, ConfigDict, Field


class AgentModelSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    machine_id: str = Field(min_length=1, max_length=100)
    model: str = Field(default='', max_length=180)


@router.put('/architecture/agents/{agent_id}/model')
def select_agent_model(agent_id: str, selection: AgentModelSelection):
    from core.agent_models import save_binding
    try:
        saved = save_binding(agent_id, selection.machine_id, selection.model)
    except HTTPException:
        raise
    except OSError as error:
        raise HTTPException(503, 'Provider non raggiungibile o stato non salvabile. Nessuna conferma di modifica.') from error
    return {'assignment': saved}
