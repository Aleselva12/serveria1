"""Compact operational capability registry for orchestration.

Built from executable contracts already registered by core.governance. This is
an orchestration view, not a second source of truth.
"""
from __future__ import annotations

ACTOR_COMPONENT = {
    "supervisor": "supervisor",
    "structure_agent": "structure_agent",
    "local_research_agent": "local_research_agent",
    "audio_agent": "audio_agent",
    "email_quotes_agent": "email_quotes_agent",
    "programmer_agent": "programmer_agent",
}

def _required_fields(schema: dict) -> list[str]:
    return [str(x) for x in schema.get("required", []) if isinstance(x, str)]

def operational_registry() -> dict:
    from core.governance import load_capabilities, executables
    from core.runtime_status import component_runtime_status
    from core.permissions import get_permission_rule
    from core.models import resolve_model

    load_capabilities()
    runtime = component_runtime_status()["components"]
    rows = []
    for key, entry in sorted(executables.items(), key=lambda item: item[1]["contract"].id):
        contract = entry["contract"]
        component = ACTOR_COMPONENT.get(contract.actor, contract.actor)
        state = runtime.get(component, {"status": "unknown", "checks": {}})
        rules = [get_permission_rule(contract.actor, action) for action in entry["actions"]]
        rules = [rule.to_dict() for rule in rules if rule]
        try:
            model = resolve_model({
                "supervisor":"supervisor",
                "structure_agent":"structure",
                "local_research_agent":"research",
                "audio_agent":"audio",
                "email_quotes_agent":"email",
                "programmer_agent":"programmer",
            }.get(contract.actor, "supervisor"))
        except Exception:
            model = None
        rows.append({
            "id": contract.id,
            "name": contract.name,
            "description": contract.description,
            "actor": contract.actor,
            "component": component,
            "connected": bool(entry["connected"]),
            "effect": contract.effect,
            "retry": contract.retry,
            "response_mode": contract.response_mode,
            "approval": contract.approval,
            "required_actions": list(contract.required_actions),
            "conditional_actions": list(contract.conditional_actions),
            "required_inputs": _required_fields(contract.input_schema),
            "input_schema": contract.input_schema,
            "output_schema": contract.output_schema,
            "permissions": rules,
            "runtime": {
                "status": state.get("status", "unknown"),
                "checks": state.get("checks", {}),
            },
            "inference": model,
            "available_now": bool(entry["connected"]) and state.get("status") in {"ready", "busy", "degraded"},
            "implementation_revision": entry["revision"],
            "contract_version": contract.version,
        })
    return {
        "version": 1,
        "source": "core.governance.executable_contracts",
        "capabilities": rows,
        "count": len(rows),
        "available": sum(1 for row in rows if row["available_now"]),
    }

def capability(identifier: str) -> dict:
    for row in operational_registry()["capabilities"]:
        if row["id"] == identifier:
            return row
    raise KeyError(identifier)
