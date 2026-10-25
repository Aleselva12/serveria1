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
    from core.audio_api import router
    problem = _assert_routes(router, [
        ("/api/v1/audio/{ident}/transcribe", "POST"),
        ("/api/v1/audio/{ident}/commercial/proposals", "POST"),
        ("/api/v1/audio/{ident}/commercial/proposals/{proposal_id}/resolve", "POST"),
    ], "Audio → approvazione")
    if problem: return problem
    from core import commercial_word, commercial_notes
    if not all(callable(getattr(commercial_word, n, None)) for n in ("parse","propose_append")):
        return "fail", "Collegamento assente: Audio → motore Word"
    if not callable(getattr(commercial_notes, "resolve_proposal", None)):
        return "fail", "Collegamento assente: approvazione → pubblicazione Word"
    return "pass", "Contratti Audio → proposta → approvazione → Word presenti"

def calendar_contract():
    from core.calendar_api import router
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
    from core.machines_api import router
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
