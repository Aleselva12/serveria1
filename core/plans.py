from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from core.orchestration import DEFAULT_PLAN_OWNER, resolve_plan_owner
from core.permissions import check_permission


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

WORKSPACE_ROOT = Path(
    os.getenv("CORA_STRUCTURE_WORKSPACE", str(PROJECT_ROOT / "structure_workspace"))
).expanduser().resolve()

PLANS_ROOT = WORKSPACE_ROOT / "plans"
EVALUATIONS_ROOT = WORKSPACE_ROOT / "evaluations"
MANAGEMENT_ROOT = WORKSPACE_ROOT / "management"

ALLOWED_ARTIFACT_TYPES = {
    "plan": PLANS_ROOT,
    "evaluation": EVALUATIONS_ROOT,
    "management": MANAGEMENT_ROOT,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_slug(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    return (normalized[:80] or fallback)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def _normalize_task(task: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": str(task.get("id") or f"task_{index:02d}"),
        "description": str(task.get("description") or "").strip(),
        "owner": DEFAULT_PLAN_OWNER,
        "target_component": str(task.get("target_component") or "unassigned").strip(),
        "dependencies": list(task.get("dependencies") or []),
        "required_actions": list(task.get("required_actions") or []),
        "expected_output": str(task.get("expected_output") or "").strip(),
        "evaluation_criteria": list(task.get("evaluation_criteria") or []),
        "status": str(task.get("status") or "planned").strip().lower(),
    }


def create_plan_record(
    *,
    objective: str,
    tasks: list[dict[str, Any]],
    priority: str = "normal",
    risks: list[str] | None = None,
    blockers: list[str] | None = None,
    checkpoints: list[str] | None = None,
    completion_criteria: list[str] | None = None,
) -> dict[str, Any]:
    now = _utc_now()
    plan_id = str(uuid.uuid4())
    owner_resolution = resolve_plan_owner(DEFAULT_PLAN_OWNER)

    return {
        "schema": "cora.plan.v1",
        "plan_id": plan_id,
        "objective": objective.strip(),
        "owner": DEFAULT_PLAN_OWNER,
        "owner_resolution": owner_resolution.to_dict(),
        "priority": priority.strip().lower() or "normal",
        "status": "planned",
        "tasks": [_normalize_task(task, i + 1) for i, task in enumerate(tasks)],
        "risks": list(risks or []),
        "blockers": list(blockers or []),
        "checkpoints": list(checkpoints or []),
        "completion_criteria": list(completion_criteria or []),
        "created_at": now,
        "updated_at": now,
    }


def save_plan_record(plan: dict[str, Any]) -> Path:
    decision = check_permission("structure_agent", "save_plan")
    if not decision.allowed:
        raise PermissionError(decision.reason)

    plan_id = str(plan["plan_id"])
    slug = _safe_slug(str(plan.get("objective", "")), "plan")
    path = PLANS_ROOT / f"{slug}__{plan_id}.json"
    _write_json(path, plan)
    return path


def create_evaluation_record(
    *,
    target: str,
    criteria: list[str],
    evidence: list[str] | None = None,
    passed: list[str] | None = None,
    failed: list[str] | None = None,
    unknown: list[str] | None = None,
    risks: list[str] | None = None,
    required_fixes: list[str] | None = None,
    recommendation: str = "",
) -> dict[str, Any]:
    now = _utc_now()
    return {
        "schema": "cora.evaluation.v1",
        "evaluation_id": str(uuid.uuid4()),
        "target": target.strip(),
        "owner": DEFAULT_PLAN_OWNER,
        "criteria": list(criteria),
        "evidence": list(evidence or []),
        "passed": list(passed or []),
        "failed": list(failed or []),
        "unknown": list(unknown or []),
        "risks": list(risks or []),
        "required_fixes": list(required_fixes or []),
        "recommendation": recommendation.strip(),
        "created_at": now,
    }


def save_evaluation_record(evaluation: dict[str, Any]) -> Path:
    decision = check_permission("structure_agent", "save_evaluation")
    if not decision.allowed:
        raise PermissionError(decision.reason)

    evaluation_id = str(evaluation["evaluation_id"])
    slug = _safe_slug(str(evaluation.get("target", "")), "evaluation")
    path = EVALUATIONS_ROOT / f"{slug}__{evaluation_id}.json"
    _write_json(path, evaluation)
    return path


def create_management_record(
    *,
    title: str,
    summary: str,
    priorities: list[str] | None = None,
    dependencies: list[str] | None = None,
    handoffs: list[dict[str, Any]] | None = None,
    next_steps: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema": "cora.management.v1",
        "management_id": str(uuid.uuid4()),
        "title": title.strip(),
        "owner": DEFAULT_PLAN_OWNER,
        "summary": summary.strip(),
        "priorities": list(priorities or []),
        "dependencies": list(dependencies or []),
        "handoffs": list(handoffs or []),
        "next_steps": list(next_steps or []),
        "created_at": _utc_now(),
    }


def save_management_record(record: dict[str, Any]) -> Path:
    decision = check_permission("structure_agent", "save_management")
    if not decision.allowed:
        raise PermissionError(decision.reason)

    record_id = str(record["management_id"])
    slug = _safe_slug(str(record.get("title", "")), "management")
    path = MANAGEMENT_ROOT / f"{slug}__{record_id}.json"
    _write_json(path, record)
    return path


def list_artifacts(artifact_type: str = "") -> list[dict[str, Any]]:
    selected_types = (
        [artifact_type.strip().lower()]
        if artifact_type.strip()
        else list(ALLOWED_ARTIFACT_TYPES)
    )
    results: list[dict[str, Any]] = []

    for selected in selected_types:
        root = ALLOWED_ARTIFACT_TYPES.get(selected)
        if root is None or not root.exists():
            continue
        for path in sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            results.append({
                "type": selected,
                "name": path.name,
                "relative_path": str(path.relative_to(WORKSPACE_ROOT)),
            })
            if len(results) >= 100:
                return results
    return results


def read_artifact(relative_path: str) -> dict[str, Any]:
    decision = check_permission("structure_agent", "read_structure_workspace")
    if not decision.allowed:
        raise PermissionError(decision.reason)

    candidate = (WORKSPACE_ROOT / relative_path).resolve()
    if candidate != WORKSPACE_ROOT and WORKSPACE_ROOT not in candidate.parents:
        raise ValueError("Percorso esterno al workspace Structure vietato.")
    if candidate.suffix.lower() != ".json":
        raise ValueError("Sono ammessi solo artefatti JSON.")
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError("Artefatto non trovato.")

    return json.loads(candidate.read_text(encoding="utf-8"))
