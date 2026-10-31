"""Shadow semantic router: learns from live traffic without controlling routing."""
from __future__ import annotations

import json
import os
from typing import Iterable

from langchain_core.messages import HumanMessage, SystemMessage

ROUTE_LABELS = (
    "direct",
    "structure",
    "research",
    "audio",
    "email",
    "programmer",
    "calendar",
    "library",
    "memory",
    "files",
    "system",
    "calculator",
    "other",
)

_TOOL_ROUTE = {
    "structure_agent_tool": "structure",
    "search_agent_tool": "research",
    "audio_agent_tool": "audio",
    "email_agent_tool": "email",
    "programmer_agent_tool": "programmer",
    "calculator_tool": "calculator",
    "system_status_tool": "system",
    "structure_registry_tool": "system",
    "recent_system_events_tool": "system",
    "owner_context_tool": "memory",
    "recall_memory_tool": "memory",
    "remember_tool": "memory",
    "forget_memory_tool": "memory",
    "list_project_files": "files",
    "read_project_file": "files",
    "library_list": "library",
    "library_search": "library",
    "library_read": "library",
}

def route_for_tool(name: str) -> str:
    if name in _TOOL_ROUTE:
        return _TOOL_ROUTE[name]
    if "calendar" in name:
        return "calendar"
    if "library" in name:
        return "library"
    return "other"

def primary_route(messages: Iterable[object]) -> str:
    """Reduce the principal orchestrator's actual first tool decision to one route label."""
    for message in messages:
        for call in list(getattr(message, "tool_calls", []) or []):
            name = call.get("name", "") if isinstance(call, dict) else str(getattr(call, "name", ""))
            if name:
                return route_for_tool(name)
    return "direct"

def _shadow_model_name() -> str:
    return os.getenv("CORA_MODEL_SHADOW_ROUTER", "qwen3:8b").strip() or "qwen3:8b"

def _parse_reply(text: str) -> tuple[str, float | None]:
    text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("ShadowRouterInvalidJSON")
        data = json.loads(text[start:end + 1])
    route = str(data.get("route", "")).strip().lower()
    if route not in ROUTE_LABELS:
        raise ValueError("ShadowRouterInvalidRoute")
    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        confidence = None
    elif confidence < 0 or confidence > 1:
        confidence = None
    return route, float(confidence) if confidence is not None else None

def predict(request_text: str) -> tuple[str, float | None, str]:
    """Run the shadow model with no tools. Failure is isolated from the live chat path."""
    from core.models import get_chat_model
    model = get_chat_model("shadow_router", temperature=0.0)
    model = model.model_copy(update={"reasoning": False, "num_predict": 96, "num_ctx": 2048})
    prompt = (
        "Sei il router shadow di Cora. Non rispondere alla richiesta e non usare tool. "
        "Classifica quale famiglia di capacità dovrebbe essere usata per prima. "
        "Route ammesse: " + ", ".join(ROUTE_LABELS) + ". "
        'Rispondi SOLO JSON: {"route":"...","confidence":0.0}. '
        "direct significa risposta diretta senza tool."
    )
    reply = model.invoke([SystemMessage(content=prompt), HumanMessage(content=request_text[:12000])])
    route, confidence = _parse_reply(str(reply.content))
    return route, confidence, _shadow_model_name()

def record_example(*, request_text: str, primary: str, thread_id: str, run_id: str) -> None:
    """Best-effort shadow inference + persistent comparison. Never raises to the caller."""
    shadow_route = None
    confidence = None
    model_name = _shadow_model_name()
    error_type = None
    try:
        shadow_route, confidence, model_name = predict(request_text)
    except Exception as error:
        error_type = type(error).__name__
    try:
        from core.database import db_connection
        with db_connection() as conn:
            conn.execute(
                """INSERT INTO shadow_router_examples
                   (thread_id,run_id,request_text,primary_route,shadow_route,agreement,
                    shadow_model,shadow_confidence,shadow_error)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (thread_id, run_id, request_text, primary, shadow_route,
                 (shadow_route == primary) if shadow_route is not None else None,
                 model_name, confidence, error_type),
            )
    except Exception:
        pass

def stats() -> dict:
    """Progress metrics; agreement with principal routing is only a provisional proxy."""
    from core.database import db_connection
    with db_connection() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS examples,
                      COUNT(*) FILTER (WHERE agreement IS NOT NULL) AS evaluated,
                      COUNT(*) FILTER (WHERE agreement IS TRUE) AS matched,
                      MAX(created_at) AS last_example
               FROM shadow_router_examples"""
        ).fetchone()
    examples = int(row["examples"] or 0)
    evaluated = int(row["evaluated"] or 0)
    matched = int(row["matched"] or 0)
    return {
        "examples": examples,
        "evaluated": evaluated,
        "matched": matched,
        "agreement_percent": round(matched * 100 / evaluated, 1) if evaluated else None,
        "last_example": row["last_example"],
        "model": _shadow_model_name(),
        "active_for_routing": False,
        "metric_label": "Accordo con orchestratore principale",
    }
