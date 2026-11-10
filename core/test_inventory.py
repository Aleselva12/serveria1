"""T11 canonical inventory of repository tests and policy for new live E2E checks.

The inventory deliberately does NOT claim that every unittest is a runtime health
check. It makes every existing test module visible to T11, and records which
ones are already executed by the one-shot verification runner.

New *live* E2E checks are constrained to the priorities selected by the owner
in problems.xlsx (2026-11-10). Existing E2E checks remain valid.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = ROOT / "tests"

PREEXISTING_LIVE_E2E_CHECKS = frozenset({
    "memory_e2e",
    "calendar_e2e",
    "worker_e2e",
    "desktop_e2e",
    "laptop_e2e",
})

# Only these roadmap points may receive NEW live E2E checks during this T11
# cleanup. This is a scope guard, not evidence that the feature already works.
TARGETED_E2E_NODES = frozenset({
    # R4.1 — Debian / systemd / administration
    "R4.1", "R4.1.p1", "R4.1.p1.m1", "R4.1.p1.m2",
    "R4.1.p2", "R4.1.p2.m1", "R4.1.p2.m2",
    "R4.1.p3", "R4.1.p3.m1", "R4.1.p3.m2",
    # R5.1 — backup and isolated restore
    "R5.1", "R5.1.p1", "R5.1.p1.m1", "R5.1.p1.m2",
    "R5.1.p2", "R5.1.p2.m1", "R5.1.p2.m2",
    # R5.2 — external apps
    "R5.2", "R5.2.p3", "R5.2.p3.m1", "R5.2.p3.m2",
    # R2.1 — duplicate customer registries
    "R2.1", "R2.1.p2", "R2.1.p2.m2",
    # T7 — memory
    "T7", "T7.p1", "T7.p2", "T7.p3", "T7.p4",
    # T1 — supervisor request ingress
    "T1", "T1.p1", "T1.p1.m1",
    # T11 — safe synthetic/E2E registry completeness
    "T11", "T11.p1", "T11.p2", "T11.p2.m2", "T11.p3", "T11.p4",
    # T9 — queues, priorities and scheduling
    "T9", "T9.p2", "T9.p2.m1", "T9.p2.m2",
    "T9.p3", "T9.p3.m1", "T9.p3.m2",
})

# Reserved names for future live E2E checks. They are not automatically added
# to CATALOG: implementation must be reviewed first and may stay absent.
TARGETED_NEW_E2E = {
    "debian_host_e2e": ("R4.1.p1", "R4.1.p1.m1", "R4.1.p1.m2"),
    "systemd_host_e2e": ("R4.1.p2", "R4.1.p2.m1", "R4.1.p2.m2"),
    "host_admin_e2e": ("R4.1.p3", "R4.1.p3.m1", "R4.1.p3.m2"),
    "backup_restore_live_e2e": ("R5.1.p1", "R5.1.p2", "R5.1.p2.m1", "R5.1.p2.m2"),
    "external_apps_release_e2e": ("R5.2.p3", "R5.2.p3.m1", "R5.2.p3.m2"),
    "customer_registry_e2e": ("R2.1.p2.m2",),
    "supervisor_ingress_e2e": ("T1.p1.m1",),
    "t11_registry_live_e2e": ("T11.p1", "T11.p2", "T11.p3"),
    "planner_queue_e2e": ("T9.p2", "T9.p3"),
}


def _test_modules() -> list[str]:
    return sorted(path.stem for path in TESTS_ROOT.glob("test_*.py") if path.is_file())


def _runner_links() -> dict[str, list[str]]:
    """Return module -> one-shot check ids without importing or running tests."""
    from deploy.verify_nodes import REGRESSIONS
    links: dict[str, list[str]] = {}
    for check_id, targets in REGRESSIONS.items():
        for target in targets:
            parts = target.split(".")
            if len(parts) < 2 or parts[0] != "tests" or not parts[1].startswith("test_"):
                continue
            links.setdefault(parts[1], []).append(check_id)
    return {module: sorted(set(checks)) for module, checks in links.items()}


def inventory() -> dict[str, Any]:
    """All current unittest modules are represented once in T11."""
    modules = _test_modules()
    links = _runner_links()
    rows = [{
        "module": module,
        "path": f"tests/{module}.py",
        "linkedChecks": links.get(module, []),
        "runnerLinked": bool(links.get(module)),
        "role": "verification_runner" if links.get(module) else "repository_test",
    } for module in modules]
    return {
        "total": len(rows),
        "runnerLinked": sum(1 for row in rows if row["runnerLinked"]),
        "repositoryOnly": sum(1 for row in rows if not row["runnerLinked"]),
        "tests": rows,
        "scope": "inventory_only",
        "note": (
            "Repository-only means visible to T11 but not automatically executed "
            "as runtime health evidence."
        ),
    }


def assert_live_e2e_scope(catalog: dict[str, dict[str, Any]]) -> None:
    """Reject new live E2E checks outside the owner-selected spreadsheet scope."""
    for check_id, item in catalog.items():
        if item.get("kind") != "e2e" or check_id in PREEXISTING_LIVE_E2E_CHECKS:
            continue
        nodes = TARGETED_NEW_E2E.get(check_id)
        if not nodes:
            raise AssertionError(
                f"New live E2E check {check_id!r} is outside the approved T11 scope"
            )
        if any(node not in TARGETED_E2E_NODES for node in nodes):
            raise AssertionError(f"Live E2E check {check_id!r} targets an unapproved node")
