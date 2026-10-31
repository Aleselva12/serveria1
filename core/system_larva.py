"""Deterministic Larva-system v0.

Observer only: it classifies already-known coordinator health signals and never
executes actions, retries work, changes policy or wakes machines.
"""
from __future__ import annotations


def evaluate(snapshot: dict) -> dict:
    issues: list[dict] = []

    ownership = snapshot.get("ownership_validation") or {}
    if ownership.get("valid") is False:
        issues.append({"severity": "critical", "code": "state_ownership_invalid"})

    permissions = (snapshot.get("permissions") or {}).get("validation") or {}
    if permissions.get("valid") is False:
        issues.append({"severity": "critical", "code": "permission_configuration_invalid"})

    runtime = snapshot.get("runtime") or {}
    if runtime.get("accepting_runs") is False:
        issues.append({"severity": "critical", "code": "runtime_not_accepting"})

    traces = snapshot.get("diagnostics") or {}
    if traces.get("write_error"):
        issues.append({"severity": "warning", "code": "trace_write_error"})
    diagnostics = traces.get("diagnostics") or {}
    if int(diagnostics.get("dropped") or 0) > 0:
        issues.append({"severity": "warning", "code": "diagnostic_events_dropped"})
    if int(diagnostics.get("write_failures") or 0) > 0:
        issues.append({"severity": "warning", "code": "diagnostic_archive_write_failures"})
    if diagnostics and diagnostics.get("worker_alive") is False:
        issues.append({"severity": "warning", "code": "diagnostic_worker_stopped"})

    severity = "critical" if any(i["severity"] == "critical" for i in issues) else "warning" if issues else "nominal"
    return {
        "version": 0,
        "mode": "observer_only",
        "status": severity,
        "issues": issues,
        "actions_taken": [],
        "may_execute_actions": False,
        "may_change_permissions": False,
        "may_schedule_workers": False,
    }
