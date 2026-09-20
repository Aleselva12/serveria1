from __future__ import annotations

import json

from langchain_core.tools import tool

from core.logging import tail_events
from core.memory import memory_stats
from core.orchestration import resolve_plan_owner
from core.permissions import check_permission, permission_manifest
from core.plans import (
    create_evaluation_record,
    create_management_record,
    create_plan_record,
    list_artifacts,
    read_artifact,
    save_evaluation_record,
    save_management_record,
    save_plan_record,
)
from core.registry import get_registry
from local_tools import list_project_files, read_project_file, system_status_tool


def _require_permission(action: str) -> None:
    decision = check_permission("structure_agent", action)
    if not decision.allowed:
        raise PermissionError(decision.reason)


@tool
def structure_components(kind: str = "") -> str:
    """
    Restituisce il registro centrale dei componenti di Cora.
    kind può essere core, agent, tool, interface oppure vuoto.
    """
    _require_permission("inspect_structure")
    normalized = kind.strip().lower() or None
    allowed = {None, "core", "agent", "tool", "interface"}
    if normalized not in allowed:
        return "Tipo non valido. Usa: core, agent, tool, interface oppure lascia vuoto."
    return json.dumps(get_registry(kind=normalized), ensure_ascii=False, indent=2)


@tool
def structure_memory_status() -> str:
    """Restituisce solo statistiche tecniche della memoria persistente."""
    _require_permission("inspect_memory_status")
    return json.dumps(memory_stats(), ensure_ascii=False, indent=2)


@tool
def structure_recent_events(
    limit: int = 30,
    event_type: str = "",
    component: str = "",
) -> str:
    """Legge eventi recenti del log strutturato per diagnosi."""
    _require_permission("inspect_events")
    events = tail_events(
        limit=max(1, min(limit, 100)),
        event_type=event_type.strip(),
        component=component.strip(),
    )
    return json.dumps(events, ensure_ascii=False, indent=2)


@tool
def structure_control_snapshot(event_limit: int = 20) -> str:
    """
    Restituisce una fotografia tecnica sintetica utile a control e management:
    componenti dichiarati, stato sistema, memoria e ultimi eventi strutturati.
    Non modifica nulla.
    """
    _require_permission("inspect_runtime")
    _require_permission("inspect_structure")
    _require_permission("inspect_memory_status")
    _require_permission("inspect_events")
    snapshot = {
        "registry": get_registry(),
        "system_status": json.loads(system_status_tool.invoke({})),
        "memory": memory_stats(),
        "recent_events": tail_events(limit=max(1, min(event_limit, 50))),
    }
    return json.dumps(snapshot, ensure_ascii=False, indent=2)


@tool
def structure_system_status() -> str:
    """Legge CPU, RAM e disco passando dal permission engine."""
    _require_permission("inspect_runtime")
    return system_status_tool.invoke({})


@tool
def structure_list_project_files(
    directory: str = ".",
    extension: str = "",
    recursive: bool = True,
) -> str:
    """Elenca file autorizzati del progetto passando dal permission engine."""
    _require_permission("list_project_files")
    return list_project_files.invoke(
        {
            "directory": directory,
            "extension": extension,
            "recursive": recursive,
        }
    )


@tool
def structure_read_project_file(relative_path: str) -> str:
    """Legge un file autorizzato del progetto passando dal permission engine."""
    _require_permission("read_project_file")
    return read_project_file.invoke({"relative_path": relative_path})


@tool
def structure_owner_status() -> str:
    """Mostra come viene risolta attualmente la ownership dei piani."""
    return json.dumps(resolve_plan_owner().to_dict(), ensure_ascii=False, indent=2)


@tool
def structure_permission_manifest() -> str:
    """Mostra le regole di permesso correnti dello Structure Agent."""
    return json.dumps(permission_manifest("structure_agent"), ensure_ascii=False, indent=2)


@tool
def structure_save_plan(
    objective: str,
    tasks: list[dict],
    priority: str = "normal",
    risks: list[str] | None = None,
    blockers: list[str] | None = None,
    checkpoints: list[str] | None = None,
    completion_criteria: list[str] | None = None,
) -> str:
    """
    Crea e salva un piano strutturato nel workspace dedicato.
    L'owner è sempre 'orchestrator'; ogni task può indicare target_component.
    """
    record = create_plan_record(
        objective=objective,
        tasks=tasks,
        priority=priority,
        risks=risks,
        blockers=blockers,
        checkpoints=checkpoints,
        completion_criteria=completion_criteria,
    )
    path = save_plan_record(record)
    return json.dumps(
        {"saved": True, "relative_path": f"plans/{path.name}", "plan": record},
        ensure_ascii=False,
        indent=2,
    )


@tool
def structure_save_evaluation(
    target: str,
    criteria: list[str],
    evidence: list[str] | None = None,
    passed: list[str] | None = None,
    failed: list[str] | None = None,
    unknown: list[str] | None = None,
    risks: list[str] | None = None,
    required_fixes: list[str] | None = None,
    recommendation: str = "",
) -> str:
    """Crea e salva una evaluation strutturata nel workspace dedicato."""
    record = create_evaluation_record(
        target=target,
        criteria=criteria,
        evidence=evidence,
        passed=passed,
        failed=failed,
        unknown=unknown,
        risks=risks,
        required_fixes=required_fixes,
        recommendation=recommendation,
    )
    path = save_evaluation_record(record)
    return json.dumps(
        {"saved": True, "relative_path": f"evaluations/{path.name}", "evaluation": record},
        ensure_ascii=False,
        indent=2,
    )


@tool
def structure_save_management(
    title: str,
    summary: str,
    priorities: list[str] | None = None,
    dependencies: list[str] | None = None,
    handoffs: list[dict] | None = None,
    next_steps: list[str] | None = None,
) -> str:
    """Salva uno stato/artefatto di management nel workspace dedicato."""
    record = create_management_record(
        title=title,
        summary=summary,
        priorities=priorities,
        dependencies=dependencies,
        handoffs=handoffs,
        next_steps=next_steps,
    )
    path = save_management_record(record)
    return json.dumps(
        {"saved": True, "relative_path": f"management/{path.name}", "management": record},
        ensure_ascii=False,
        indent=2,
    )


@tool
def structure_list_artifacts(artifact_type: str = "") -> str:
    """Elenca plan, evaluation e management artifact salvati."""
    return json.dumps(list_artifacts(artifact_type), ensure_ascii=False, indent=2)


@tool
def structure_read_artifact(relative_path: str) -> str:
    """Legge un artefatto JSON dal workspace Structure."""
    return json.dumps(read_artifact(relative_path), ensure_ascii=False, indent=2)


STRUCTURE_TOOLS = [
    structure_components,
    structure_system_status,
    structure_memory_status,
    structure_recent_events,
    structure_control_snapshot,
    structure_owner_status,
    structure_permission_manifest,
    structure_save_plan,
    structure_save_evaluation,
    structure_save_management,
    structure_list_artifacts,
    structure_read_artifact,
    structure_list_project_files,
    structure_read_project_file,
]
