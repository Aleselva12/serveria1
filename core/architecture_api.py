"""Read-only topology extracted from the executable compiled LangGraphs."""
import hashlib
import importlib
import json
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
