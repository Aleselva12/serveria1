"""Non-destructive boundary checks: pinpoint the broken hop, NOT end-to-end proof."""
from __future__ import annotations


def _routes(router):
    return {(r.path, method) for r in router.routes for method in (getattr(r, "methods", None) or ())}

def _assert_routes(router, expected, stage):
    found = _routes(router)
    for path, method in expected:
        if (path, method) not in found:
            return "fail", "Collegamento assente: " + stage + " → " + method + " " + path
    return None

def chat_contract():
    from api import app
    problem = _assert_routes(app, [
        ("/api/v1/chat/runs", "POST"), ("/chat", "POST"),
    ], "UI/Chat → API")
    if problem: return problem
    from graph import graph, supervisor_tools
    nodes = set(graph.get_graph().nodes)
    for node in ("prepare", "agent", "tools"):
        if node not in nodes: return "fail", "Collegamento assente: grafo → " + node
    edges = {(e.source, e.target) for e in graph.get_graph().edges}
    if ("prepare", "agent") not in edges or ("agent", "tools") not in edges:
        return "fail", "Collegamento assente: preparazione → orchestratore → tool"
    available = {tool.name for tool in supervisor_tools}
    for name in ("audio_agent_tool", "email_agent_tool", "search_agent_tool", "structure_agent_tool", "programmer_agent_tool"):
        if name not in available:
            return "fail", "Delega mancante: orchestratore → " + name
    return "pass", "Contratti Chat → grafo → tool delegati presenti; nessuna inferenza eseguita"

def audio_word_contract():
    from core.api.audio_api import router
    problem = _assert_routes(router, [
        ("/api/v1/audio/{ident}/transcribe", "POST"),
        ("/api/v1/audio/{ident}/commercial/proposals", "POST"),
        ("/api/v1/audio/{ident}/commercial/proposals/{proposal_id}/resolve", "POST"),
    ], "Audio → approvazione")
    if problem: return problem
    from core import commercial_notes, commercial_word
    if not all(callable(getattr(commercial_word, n, None)) for n in ("parse","propose_append")):
        return "fail", "Collegamento assente: Audio → motore Word"
    if not callable(getattr(commercial_notes, "resolve_proposal", None)):
        return "fail", "Collegamento assente: approvazione → pubblicazione Word"
    return "pass", "Contratti Audio → proposta → approvazione → Word presenti"

def calendar_contract():
    from core.api.calendar_api import router
    problem = _assert_routes(router, [
        ("/api/v1/calendar/events", "POST"),
        ("/api/v1/calendar/events/{event_id}", "PATCH"),
        ("/api/v1/calendar/proposals/{proposal_id}/resolve", "POST"),
    ], "Calendario → approvazione")
    if problem: return problem
    from core import google_calendar
    if not all(callable(getattr(google_calendar,n,None)) for n in ("create_event","update_event","delete_event")):
        return "fail", "Collegamento assente: Calendar API → Google"
    return "pass", "Contratti Calendario → proposte → Google presenti; OAuth non provato"

def worker_contract():
    from core.api.machines_api import router
    problem = _assert_routes(router, [
        ("/api/v1/machines/{machine_id}/generate", "POST"),
        ("/api/v1/machines/{machine_id}/test", "POST"),
        ("/api/v1/machines/{machine_id}/models", "GET"),
    ], "Orchestratore → worker")
    if problem: return problem
    from core.agent_models import binding, remote_ready
    if not callable(binding) or not callable(remote_ready):
        return "fail", "Collegamento assente: modello agente → macchina"
    return "pass", "Contratti macchina, modello e bridge presenti; inferenza non provata"


def orchestrator_v1_contract():
    """Structural W1 proof without importing the global FastAPI app or causing side effects."""
    from core.api.orchestration_api import router as orchestration_router
    problem = _assert_routes(orchestration_router, [
        ("/api/v1/runtime/capabilities", "GET"),
        ("/api/v1/runtime/coordinator", "GET"),
        ("/api/v1/runtime/context-contracts", "GET"),
    ], "Orchestratore V1 → router dedicato")
    if problem: return problem

    from core.api.runtime_api import router as runtime_router
    problem = _assert_routes(runtime_router, [
        ("/api/v1/runtime/diagnostics", "GET"),
    ], "Orchestratore V1 → diagnostica runtime")
    if problem: return problem

    from core.system_coordinator import validate_ownership
    ownership = validate_ownership()
    if not ownership.get("valid"):
        return "fail", "Ownership stato non coerente nel System Coordinator"

    from core.registry import get_component
    for component_id in ("system_coordinator", "system_larva", "permission_engine"):
        component = get_component(component_id)
        if not component or not component.get("available"):
            return "fail", "Componente orchestrazione non disponibile: " + component_id

    from core.component_bus import component_bus
    if not callable(getattr(component_bus, "dispatch_capability", None)):
        return "fail", "Component Bus non espone dispatch_capability"

    from core.operational_capabilities import operational_registry
    if not callable(operational_registry):
        return "fail", "Capability Registry operativo non disponibile"

    from core.run_states import TRANSITIONS
    required_states = {"queued", "running", "cancelling", "completed", "failed", "awaiting_approval"}
    known_states = set(TRANSITIONS) | {state for targets in TRANSITIONS.values() for state in targets}
    if not required_states <= known_states:
        return "fail", "State Machine incompleta per la base orchestrazione"

    from core.context_contracts import ContextPacket, ContextRequest
    if ContextRequest.model_json_schema().get("title") != "ContextRequest":
        return "fail", "Contratto ContextRequest non disponibile"
    if ContextPacket.model_json_schema().get("title") != "ContextPacket":
        return "fail", "Contratto ContextPacket non disponibile"

    from core.error_decisions import decide
    expected = {
        ("ok", None): "complete",
        ("pending", None): "needs_approval",
        ("uncertain", "EffectUncertain"): "effect_uncertain",
    }
    for (status, code), decision in expected.items():
        if decide(status=status, error_code=code) != decision:
            return "fail", "Classificazione errori orchestrazione incoerente"

    return "pass", "Orchestratore V1 collegato: router, Coordinator, Bus, permessi, contesto, diagnostica e decisioni standard"

