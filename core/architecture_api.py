"""Agent catalog and owner model assignment; legacy topology remains read-only."""
import hashlib
import importlib
import json
from functools import lru_cache
from fastapi import APIRouter, HTTPException, Query
from core.execution_traces import read_runs

router = APIRouter(prefix="/api/v1", tags=["Architecture"])


@router.get('/architecture/worker-update')
def worker_update():
    """Fixed source bundle from this installed release; never includes secrets."""
    import io
    import zipfile
    from pathlib import Path
    from fastapi.responses import Response
    root = Path(__file__).resolve().parents[1] / 'worker'
    data = io.BytesIO()
    try:
        with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in ('worker.py', 'Dockerfile', 'compose.yml', 'UPDATE.md'):
                archive.writestr(name, (root / name).read_bytes())
    except OSError as error:
        raise HTTPException(503, 'Sorgenti worker mancanti: aggiorna Cora prima di scaricare il pacchetto.') from error
    return Response(data.getvalue(), media_type='application/zip', headers={
        'Content-Disposition': 'attachment; filename="cora-worker-update.zip"', 'Cache-Control': 'no-store'})
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


@router.get("/architecture/shadow-router")
def shadow_router_status():
    """Training progress for the non-authoritative shadow router."""
    from core.models import resolve_model
    from core.shadow_router import stats
    principal = resolve_model("supervisor")
    shadow = resolve_model("shadow_router")
    try:
        progress = stats()
        database_ready = True
        error = None
    except Exception as exc:
        progress = {
            "examples": 0, "evaluated": 0, "matched": 0,
            "agreement_percent": None, "last_example": None,
            "model": shadow["model"], "active_for_routing": False,
            "metric_label": "Accordo con orchestratore principale",
        }
        database_ready = False
        error = type(exc).__name__
    return {
        "principal": principal,
        "shadow": shadow,
        "progress": progress,
        "database_ready": database_ready,
        "error": error,
        "note": "Il router specializzato lavora in shadow mode: osserva e confronta, ma non decide il routing reale.",
    }


@router.get('/architecture/agents')
def agents_catalog():
    from core.agent_models import ROLES, bindings
    from core.registry import get_registry
    from core.models import resolve_model
    from core.model_evidence import observations
    from core.tool_inventory import inventory, SOURCES
    from core.runtime_status import component_runtime_status
    from core.machines_api import _read
    configured = bindings()
    last_replies = observations()
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
        resolved = resolve_model(ROLES[identifier])
        machine = resolved['machine_id']
        agents.append({**component, 'role': ROLES[identifier], 'model': resolved['model'], 'configuration': resolved,
                       'last_inference': last_replies.get(ROLES[identifier]),
                       'entrypoint': 'Chat principale' if identifier == 'supervisor' else 'Programma / Copilot e delega da Cora' if identifier == 'programmer_agent' else 'Delega da Cora centrale',
                       'assignment': assignment, 'machine_name': 'Ollama di Cora' if machine == 'local' else machines.get(machine, 'Worker non registrato'),
                       'runtime': runtime.get(identifier, {'status': 'unknown', 'checks': {}}),
                       'tools': [e for e in tools['entries'] if e['kind'] == 'tool' and owners[identifier] in e['agents']]})
    from core.audio_api import audio_status
    audio = next((a for a in agents if a['id'] == 'audio_agent'), None)
    if audio is not None: audio['transcription'] = audio_status()
    return {'agents': agents, 'components': [c for c in registry['components'] if c['kind'] == 'core' and c['id'] not in ROLES],
            'inventory_errors': tools['errors']}


@router.get('/architecture/default-models')
def default_models_status():
    from core.default_models import status
    try:
        return status()
    except Exception as error:
        raise HTTPException(503, 'Impossibile leggere i modelli locali di Ollama.') from error


@router.post('/architecture/default-models/download/{pack}', status_code=202)
def download_default_models(pack: str):
    from core.default_models import start_download
    try:
        return start_download(pack)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except Exception as error:
        raise HTTPException(503, 'Download modelli non avviato: verifica Ollama e la connessione del server.') from error


@router.get('/architecture/model-targets')
def model_targets():
    from core.machines_api import _read, _settings
    return {'targets': [dict(id='local', name='Ollama di Cora', enabled=True, active_model=None)] + [
        dict(id=m['id'], name=m['name'], enabled=_settings(m)['enabled'],
             active_model=_settings(m)['selected_model']) for m in _read()]}


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
    active_model = settings['selected_model']
    # Only the model explicitly selected in Macchine can be used by agents.
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
    from core.models import resolve_model
    from core.agent_models import ROLES
    return {'assignment': saved, 'configuration': resolve_model(ROLES[agent_id]),
            'applies': 'next_model_call', 'requires_restart': False}


@router.post('/architecture/agents/{agent_id}/verify', status_code=202)
def verify_agent_model(agent_id: str):
    from core.agent_models import ROLES
    from core.models import get_chat_model, resolve_model
    from core.runtime import runtime
    if agent_id not in ROLES:
        raise HTTPException(404, 'Agente non trovato.')
    role = ROLES[agent_id]
    expected = resolve_model(role)
    if expected['machine_id'] != 'local':
        from core.agent_models import remote_machine, require_agent_chat
        require_agent_chat(remote_machine(expected['machine_id'], expected['model']))
    def work(run):
        import time
        from langchain_core.messages import HumanMessage
        from core.runtime import checkpoint
        checkpoint()
        # Resolve only when this queued job actually starts. Never bind tools.
        model = get_chat_model(role)
        if model.configuration_id != expected['configuration_id']:
            raise RuntimeError('Configurazione cambiata prima della verifica: ricarica e riprova.')
        model = model.model_copy(update={'reasoning': False, 'num_predict': 16, 'num_ctx': 2048})
        started = time.monotonic()
        from core.execution_traces import ExecutionTrace
        trace = ExecutionTrace(run.thread_id, run.graph_version) if run is not None else None
        reply = model.invoke([HumanMessage(content='Rispondi solo OK.')], config={'callbacks': [trace] if trace else []})
        checkpoint()
        metadata = reply.response_metadata
        # model_name may be synthesized by LangChain from the requested model.
        # Only Ollama's native model field is provider evidence.
        reported = metadata.get('model')
        if not isinstance(reported, str): reported = None
        from core.model_evidence import matches_requested
        return {'configuration': expected, 'reported_model': reported, 'matches_requested': matches_requested(expected['model'], reported),
                'provider_reported': bool(reported), 'duration_ms': round((time.monotonic()-started)*1000, 2),
                'tools_executed': False}
    try:
        run = runtime.submit('verify-model:' + agent_id, work, kind='model_verification', target=agent_id)
    except (ValueError, RuntimeError) as error:
        raise HTTPException(409, str(error)) from error
    return {'run_id': run.id, 'configuration': expected}
