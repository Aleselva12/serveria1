"""Read-only coordination view for Cora's internal orchestration.

This module does not execute actions or choose routes. It makes ownership of
runtime state explicit and exposes one diagnostic snapshot over existing cores.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class StateOwner:
    concern: str
    authority: str
    durable: bool
    purpose: str
    replicas: tuple[str, ...] = ()


STATE_OWNERSHIP: tuple[StateOwner, ...] = (
    StateOwner(
        "task_lifecycle",
        "runtime_runs (PostgreSQL) via core.run_lifecycle",
        True,
        "Stato canonico di root run e child run, revisioni, cancellazioni ed esiti.",
        ("core.runtime.Run", "working_memory status", "diagnostic events"),
    ),
    StateOwner(
        "live_execution",
        "core.runtime.Run",
        False,
        "Stato effimero del worker Python durante l'esecuzione corrente.",
        ("runtime_runs",),
    ),
    StateOwner(
        "component_exchange",
        "TaskEnvelope / ComponentResult via core.component_bus",
        False,
        "Contratto tipizzato per richieste e risultati tra componenti nello stesso processo.",
        ("component bus snapshot",),
    ),
    StateOwner(
        "critical_events",
        "domain events (PostgreSQL)",
        True,
        "Eventi transazionali che descrivono cambiamenti critici di run e operazioni.",
        ("EventBus live stream", "diagnostic archive"),
    ),
    StateOwner(
        "live_events",
        "core.event_bus.EventBus",
        False,
        "Streaming/replay limitato del processo corrente; non è la fonte autorevole storica.",
        ("diagnostic archive",),
    ),
    StateOwner(
        "diagnostics",
        "diagnostic_events (PostgreSQL) via core.observability",
        True,
        "Telemetria best-effort e metadati tecnici per Attività/diagnostica.",
        ("EventBus", "execution traces"),
    ),
    StateOwner(
        "working_memory",
        "working_memory (PostgreSQL)",
        True,
        "Stato operativo temporaneo per agente/thread; non sostituisce il lifecycle del run.",
        ("core.runtime.Run",),
    ),
    StateOwner(
        "persistent_memory",
        "memories / episodes / system context (PostgreSQL)",
        True,
        "Memoria cognitiva persistente, separata da cronologia e diagnostica.",
    ),
    StateOwner(
        "permissions",
        "core.permissions + action_approvals (PostgreSQL)",
        True,
        "Regole deterministiche e richieste di approvazione; nessun modello può sovrascriverle.",
    ),
    StateOwner(
        "resource_assignment",
        "machines registry + agent model bindings",
        True,
        "Scelte manuali correnti di worker/modelli. Nessuno scheduler autonomo è autorevole oggi.",
    ),
    StateOwner(
        "context_selection",
        "core.context_pages / core.context_budget",
        False,
        "Selezione e riduzione del contesto per la singola richiesta; il Context Manager globale è ancora da definire.",
    ),
)


def ownership_manifest() -> list[dict]:
    return [asdict(row) for row in STATE_OWNERSHIP]


def validate_ownership() -> dict:
    concerns = [row.concern for row in STATE_OWNERSHIP]
    duplicated = sorted({name for name in concerns if concerns.count(name) > 1})
    return {
        "valid": not duplicated,
        "duplicate_concerns": duplicated,
        "count": len(STATE_OWNERSHIP),
    }


def snapshot() -> dict:
    """Aggregate existing state without introducing a second source of truth."""
    from core.runtime import runtime
    from core.event_bus import bus
    from core.database import pool_stats
    from core.execution_traces import trace_status
    from core.component_bus import component_bus
    from core.permissions import permission_manifest, validate_permission_configuration

    rules = permission_manifest()
    policies = {}
    for row in rules:
        policy = str(row.get("policy", "unknown"))
        policies[policy] = policies.get(policy, 0) + 1

    result = {
        "version": 1,
        "mode": "read_only_coordinator",
        "ownership": ownership_manifest(),
        "ownership_validation": validate_ownership(),
        "runtime": {
            "accepting_runs": not runtime.closed,
            "active_runs": len(runtime.snapshot()),
            "worker_slots": 1,
        },
        "component_bus": {
            "components": component_bus.snapshot(),
            "transport": "in_process",
        },
        "event_bus": {
            "process_id": bus.process_id,
            "sequence": bus.sequence,
            "capacity": bus.events.maxlen,
            "transport": "in_process",
            "authoritative_history": False,
        },
        "database_pool": pool_stats(),
        "permissions": {
            "rules": len(rules),
            "policies": policies,
            "validation": validate_permission_configuration(),
        },
        "diagnostics": trace_status(),
        "guarantees": {
            "changes_state": False,
            "routes_user_requests": False,
            "schedules_workers": False,
            "executes_tools": False,
        },
    }
    from core.system_larva import evaluate
    result["larva"] = evaluate(result)
    return result
