from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum, IntEnum


class PermissionLevel(IntEnum):
    OBSERVE = 0
    READ = 1
    DRAFT = 2
    WRITE = 3
    EXECUTE = 4
    ADMIN = 5


class ApprovalPolicy(str, Enum):
    AUTO = "auto"
    CONFIRM = "confirm"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ActionPermission:
    actor: str
    action: str
    level: PermissionLevel
    policy: ApprovalPolicy
    scope: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["level"] = self.level.name.lower()
        data["policy"] = self.policy.value
        return data


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    requires_user_confirmation: bool
    reason: str
    rule: ActionPermission | None

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "requires_user_confirmation": self.requires_user_confirmation,
            "reason": self.reason,
            "rule": self.rule.to_dict() if self.rule else None,
        }


STRUCTURE_AGENT_RULES: tuple[ActionPermission, ...] = (
    ActionPermission("structure_agent", "inspect_structure", PermissionLevel.OBSERVE, ApprovalPolicy.AUTO),
    ActionPermission("structure_agent", "inspect_runtime", PermissionLevel.OBSERVE, ApprovalPolicy.AUTO),
    ActionPermission("structure_agent", "inspect_events", PermissionLevel.OBSERVE, ApprovalPolicy.AUTO),
    ActionPermission("structure_agent", "inspect_memory_status", PermissionLevel.OBSERVE, ApprovalPolicy.AUTO),
    ActionPermission("structure_agent", "list_project_files", PermissionLevel.READ, ApprovalPolicy.AUTO),
    ActionPermission("structure_agent", "read_project_file", PermissionLevel.READ, ApprovalPolicy.AUTO),
    ActionPermission("structure_agent", "read_structure_workspace", PermissionLevel.READ, ApprovalPolicy.AUTO, "structure_workspace"),
    ActionPermission("structure_agent", "create_plan", PermissionLevel.DRAFT, ApprovalPolicy.AUTO),
    ActionPermission("structure_agent", "create_evaluation", PermissionLevel.DRAFT, ApprovalPolicy.AUTO),
    ActionPermission("structure_agent", "create_management", PermissionLevel.DRAFT, ApprovalPolicy.AUTO),
    ActionPermission("structure_agent", "save_plan", PermissionLevel.WRITE, ApprovalPolicy.AUTO, "structure_workspace/plans"),
    ActionPermission("structure_agent", "save_evaluation", PermissionLevel.WRITE, ApprovalPolicy.AUTO, "structure_workspace/evaluations"),
    ActionPermission("structure_agent", "save_management", PermissionLevel.WRITE, ApprovalPolicy.AUTO, "structure_workspace/management"),
    ActionPermission("structure_agent", "modify_source_code", PermissionLevel.WRITE, ApprovalPolicy.BLOCKED),
    ActionPermission("structure_agent", "modify_core_configuration", PermissionLevel.ADMIN, ApprovalPolicy.BLOCKED),
    ActionPermission("structure_agent", "write_persistent_memory", PermissionLevel.WRITE, ApprovalPolicy.BLOCKED),
    ActionPermission("structure_agent", "external_action", PermissionLevel.EXECUTE, ApprovalPolicy.BLOCKED),
)


RULES: tuple[ActionPermission, ...] = STRUCTURE_AGENT_RULES


def get_permission_rule(actor: str, action: str) -> ActionPermission | None:
    normalized_actor = actor.strip().lower()
    normalized_action = action.strip().lower()

    for rule in RULES:
        if rule.actor == normalized_actor and rule.action == normalized_action:
            return rule
    return None


def check_permission(
    actor: str,
    action: str,
    *,
    user_approved: bool = False,
) -> PermissionDecision:
    """
    Deterministic permission check.

    User approval can satisfy CONFIRM rules. BLOCKED rules stay blocked until
    the configured policy is deliberately changed; an agent cannot self-elevate.
    """
    rule = get_permission_rule(actor, action)
    if rule is None:
        return PermissionDecision(
            allowed=False,
            requires_user_confirmation=False,
            reason="Nessuna regola di permesso definita per questa azione.",
            rule=None,
        )

    if rule.policy is ApprovalPolicy.AUTO:
        return PermissionDecision(True, False, "Azione autorizzata automaticamente.", rule)

    if rule.policy is ApprovalPolicy.CONFIRM:
        if user_approved:
            return PermissionDecision(True, False, "Azione autorizzata dall'utente.", rule)
        return PermissionDecision(False, True, "È richiesta conferma esplicita dell'utente.", rule)

    return PermissionDecision(
        False,
        False,
        "Azione bloccata dalla policy corrente.",
        rule,
    )


def permission_manifest(actor: str = "") -> list[dict]:
    normalized = actor.strip().lower()
    selected = [rule for rule in RULES if not normalized or rule.actor == normalized]
    return [rule.to_dict() for rule in selected]
