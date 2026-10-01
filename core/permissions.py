from __future__ import annotations

from collections import Counter
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


# Politiche iniziali conservative ma utilizzabili.
# Verranno raffinate insieme alle pagine/approval UI. L'obiettivo attuale è che
# ogni azione esistente passi comunque da un allowlist deterministico.
SUPERVISOR_RULES: tuple[ActionPermission, ...] = (
    ActionPermission("supervisor", "calculate", PermissionLevel.OBSERVE, ApprovalPolicy.AUTO),
    ActionPermission("supervisor", "inspect_runtime", PermissionLevel.OBSERVE, ApprovalPolicy.AUTO),
    ActionPermission("supervisor", "list_project_files", PermissionLevel.READ, ApprovalPolicy.AUTO),
    ActionPermission("supervisor", "read_project_file", PermissionLevel.READ, ApprovalPolicy.AUTO),
    ActionPermission("supervisor", "inspect_structure", PermissionLevel.READ, ApprovalPolicy.AUTO),
    ActionPermission("supervisor", "inspect_events", PermissionLevel.READ, ApprovalPolicy.AUTO),
    ActionPermission("supervisor", "recall_memory", PermissionLevel.READ, ApprovalPolicy.AUTO),
    ActionPermission(
        "supervisor",
        "remember_memory",
        PermissionLevel.WRITE,
        ApprovalPolicy.AUTO,
        "persistent_memory",
        "Temporaneo: il prompt richiede una richiesta esplicita dell'utente.",
    ),
    ActionPermission(
        "supervisor",
        "forget_memory",
        PermissionLevel.WRITE,
        ApprovalPolicy.AUTO,
        "persistent_memory",
        "Temporaneo: il prompt richiede una richiesta esplicita dell'utente.",
    ),
    ActionPermission("supervisor", "delegate_structure", PermissionLevel.EXECUTE, ApprovalPolicy.AUTO),
    ActionPermission("supervisor", "delegate_research", PermissionLevel.EXECUTE, ApprovalPolicy.AUTO),
    ActionPermission("supervisor", "delegate_audio", PermissionLevel.EXECUTE, ApprovalPolicy.AUTO),
    ActionPermission("supervisor", "delegate_email", PermissionLevel.EXECUTE, ApprovalPolicy.AUTO),
)


STRUCTURE_AGENT_RULES: tuple[ActionPermission, ...] = (
    ActionPermission("structure_agent", "inspect_structure", PermissionLevel.OBSERVE, ApprovalPolicy.AUTO),
    ActionPermission("structure_agent", "inspect_runtime", PermissionLevel.OBSERVE, ApprovalPolicy.AUTO),
    ActionPermission("structure_agent", "inspect_events", PermissionLevel.OBSERVE, ApprovalPolicy.AUTO),
    ActionPermission("structure_agent", "inspect_memory_status", PermissionLevel.OBSERVE, ApprovalPolicy.AUTO),
    ActionPermission("structure_agent", "inspect_owner", PermissionLevel.OBSERVE, ApprovalPolicy.AUTO),
    ActionPermission("structure_agent", "inspect_permissions", PermissionLevel.OBSERVE, ApprovalPolicy.AUTO),
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


RESEARCH_AGENT_RULES: tuple[ActionPermission, ...] = (
    ActionPermission("local_research_agent", "list_documents", PermissionLevel.READ, ApprovalPolicy.AUTO, "knowledge_root"),
    ActionPermission("local_research_agent", "search_documents", PermissionLevel.READ, ApprovalPolicy.AUTO, "knowledge_root"),
    ActionPermission("local_research_agent", "read_document", PermissionLevel.READ, ApprovalPolicy.AUTO, "knowledge_root"),
    ActionPermission(
        "local_research_agent",
        "create_word_document",
        PermissionLevel.WRITE,
        ApprovalPolicy.AUTO,
        "knowledge_root",
        "Temporaneo: creazione consentita solo nel knowledge root autorizzato.",
    ),
    ActionPermission(
        "local_research_agent",
        "append_word_document",
        PermissionLevel.WRITE,
        ApprovalPolicy.AUTO,
        "knowledge_root",
        "Aggiornamento non distruttivo: aggiunge contenuto senza riscrivere il documento.",
    ),
    ActionPermission(
        "local_research_agent",
        "overwrite_word_document",
        PermissionLevel.WRITE,
        ApprovalPolicy.BLOCKED,
        "knowledge_root",
        "La sovrascrittura distruttiva resta bloccata finché non esiste un flusso di conferma dedicato.",
    ),
)


AUDIO_AGENT_RULES: tuple[ActionPermission, ...] = (
    ActionPermission("audio_agent", "list_audio", PermissionLevel.READ, ApprovalPolicy.AUTO, "audio_root"),
    ActionPermission("audio_agent", "transcribe_audio", PermissionLevel.EXECUTE, ApprovalPolicy.AUTO, "audio_root"),
    ActionPermission(
        "audio_agent",
        "save_transcript",
        PermissionLevel.WRITE,
        ApprovalPolicy.AUTO,
        "transcript_root",
        "Temporaneo: il prompt richiede una richiesta esplicita di salvataggio.",
    ),
)


EMAIL_AGENT_RULES: tuple[ActionPermission, ...] = (
    ActionPermission("email_quotes_agent", "search_email", PermissionLevel.READ, ApprovalPolicy.AUTO, "gmail"),
    ActionPermission("email_quotes_agent", "read_email", PermissionLevel.READ, ApprovalPolicy.AUTO, "gmail"),
    ActionPermission("email_quotes_agent", "read_daily_email", PermissionLevel.READ, ApprovalPolicy.AUTO, "gmail"),
    ActionPermission(
        "email_quotes_agent",
        "save_email_draft",
        PermissionLevel.WRITE,
        ApprovalPolicy.AUTO,
        "gmail_drafts",
        "Temporaneo: crea soltanto bozze e il prompt richiede una richiesta esplicita.",
    ),
    ActionPermission(
        "email_quotes_agent",
        "generate_quote_pdf",
        PermissionLevel.WRITE,
        ApprovalPolicy.AUTO,
        "quote_root",
    ),
    ActionPermission(
        "email_quotes_agent",
        "send_email",
        PermissionLevel.EXECUTE,
        ApprovalPolicy.BLOCKED,
        "gmail",
        "L'invio automatico di email non è consentito.",
    ),
)


RULES: tuple[ActionPermission, ...] = (
    SUPERVISOR_RULES
    + STRUCTURE_AGENT_RULES
    + RESEARCH_AGENT_RULES
    + AUDIO_AGENT_RULES
    + EMAIL_AGENT_RULES
)


EXPECTED_ACTIONS: dict[str, set[str]] = {
    "supervisor": {
        "calculate",
        "inspect_runtime",
        "list_project_files",
        "read_project_file",
        "inspect_structure",
        "inspect_events",
        "recall_memory",
        "remember_memory",
        "forget_memory",
        "delegate_structure",
        "delegate_research",
        "delegate_audio",
        "delegate_email",
    },
    "structure_agent": {
        "inspect_structure",
        "inspect_runtime",
        "inspect_events",
        "inspect_memory_status",
        "inspect_owner",
        "inspect_permissions",
        "list_project_files",
        "read_project_file",
        "read_structure_workspace",
        "create_plan",
        "create_evaluation",
        "create_management",
        "save_plan",
        "save_evaluation",
        "save_management",
        "modify_source_code",
        "modify_core_configuration",
        "write_persistent_memory",
        "external_action",
    },
    "local_research_agent": {
        "list_documents",
        "search_documents",
        "read_document",
        "create_word_document",
        "append_word_document",
        "overwrite_word_document",
    },
    "audio_agent": {
        "list_audio",
        "transcribe_audio",
        "save_transcript",
    },
    "email_quotes_agent": {
        "search_email",
        "read_email",
        "read_daily_email",
        "save_email_draft",
        "generate_quote_pdf",
        "send_email",
    },
}


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


def require_permission(
    actor: str,
    action: str,
    *,
    user_approved: bool = False,
) -> PermissionDecision:
    """Return the decision or raise PermissionError when the action cannot run."""
    decision = check_permission(actor, action, user_approved=user_approved)
    if not decision.allowed:
        raise PermissionError(decision.reason)
    return decision


def permission_manifest(actor: str = "") -> list[dict]:
    normalized = actor.strip().lower()
    selected = [rule for rule in RULES if not normalized or rule.actor == normalized]
    return [rule.to_dict() for rule in selected]


def validate_permission_configuration() -> dict:
    """Validate duplicate rules and coverage of the actions currently implemented."""
    keys = [(rule.actor, rule.action) for rule in RULES]
    duplicates = [
        {"actor": actor, "action": action}
        for (actor, action), count in Counter(keys).items()
        if count > 1
    ]

    configured_by_actor: dict[str, set[str]] = {}
    for rule in RULES:
        configured_by_actor.setdefault(rule.actor, set()).add(rule.action)

    missing: list[dict[str, str]] = []
    for actor, expected in EXPECTED_ACTIONS.items():
        configured = configured_by_actor.get(actor, set())
        for action in sorted(expected - configured):
            missing.append({"actor": actor, "action": action})

    return {
        "valid": not duplicates and not missing,
        "rule_count": len(RULES),
        "actors": sorted(configured_by_actor),
        "duplicates": duplicates,
        "missing": missing,
    }
