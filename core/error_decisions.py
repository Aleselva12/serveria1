"""Standard orchestration decisions derived from technical/capability outcomes."""
from __future__ import annotations

from typing import Literal

Decision = Literal[
    "complete",
    "retry_safe",
    "needs_replan",
    "needs_approval",
    "resource_unavailable",
    "effect_uncertain",
    "cancelled",
    "fatal",
]

_RESOURCE_ERRORS = {
    "HTTPException",
    "ConnectionError",
    "TimeoutError",
    "URLError",
    "ModelConfigurationChanged",
    "ModelToolsUnsupported",
    "DatabaseNotConfigured",
}
_REPLAN_ERRORS = {
    "ValidationError",
    "ToolReportedError",
    "ContextOverflow",
    "ModelEmptyResponse",
    "KeyError",
}
_UNCERTAIN_ERRORS = {"EffectUncertain", "OperationConflict", "DurabilityLost"}
_CANCEL_ERRORS = {"RunStopped", "RunCancelled", "CancelledError"}


def decide(*, status: str, error_code: str | None = None, effect: str = "compute", retry: str = "never") -> Decision:
    """Map a concrete outcome to one small orchestration decision vocabulary."""
    if status in {"ok", "completed", "succeeded"}:
        return "complete"
    if status in {"pending", "waiting_approval", "awaiting_approval"}:
        return "needs_approval"
    code = (error_code or "").strip()
    if code in _CANCEL_ERRORS or status in {"cancelled", "timed_out"}:
        return "cancelled"
    if code in _UNCERTAIN_ERRORS or status == "uncertain":
        return "effect_uncertain"
    if code in _RESOURCE_ERRORS:
        return "resource_unavailable"
    if code in _REPLAN_ERRORS:
        return "needs_replan"
    if retry == "safe" and effect in {"read", "compute"}:
        return "retry_safe"
    if status == "failed":
        return "needs_replan"
    return "fatal"


def explanation(decision: Decision) -> str:
    return {
        "complete": "Operazione completata.",
        "retry_safe": "Il fallimento riguarda un'operazione dichiarata ripetibile in sicurezza.",
        "needs_replan": "Il piano o i parametri devono essere rivisti prima di riprovare.",
        "needs_approval": "L'azione richiede una decisione esplicita del proprietario.",
        "resource_unavailable": "Una risorsa, un modello, un worker o un servizio necessario non è disponibile.",
        "effect_uncertain": "Un effetto potrebbe essere già avvenuto: non ripetere automaticamente.",
        "cancelled": "L'esecuzione è stata annullata o ha superato il limite temporale.",
        "fatal": "Errore non classificato come recuperabile automaticamente.",
    }[decision]
