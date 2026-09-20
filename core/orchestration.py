from __future__ import annotations

from dataclasses import asdict, dataclass


DEFAULT_PLAN_OWNER = "orchestrator"


@dataclass(frozen=True)
class OwnerResolution:
    owner: str
    backend: str
    available: bool
    note: str

    def to_dict(self) -> dict:
        return asdict(self)


def resolve_plan_owner(owner: str = DEFAULT_PLAN_OWNER) -> OwnerResolution:
    """
    Resolve the conceptual plan owner.

    The biological/lightweight orchestrator does not exist yet. Until it does,
    Cora keeps the owner identity stable and uses a deterministic fallback for
    plan bookkeeping only. This function does not execute tasks.
    """
    normalized = (owner or DEFAULT_PLAN_OWNER).strip().lower()

    if normalized == DEFAULT_PLAN_OWNER:
        return OwnerResolution(
            owner=DEFAULT_PLAN_OWNER,
            backend="deterministic_fallback",
            available=False,
            note=(
                "L'orchestratore neurale non è ancora implementato. "
                "Il fallback mantiene ownership e metadati del piano, "
                "ma non esegue né instrada autonomamente i task."
            ),
        )

    return OwnerResolution(
        owner=normalized,
        backend="declared_owner",
        available=False,
        note="Owner dichiarato ma non collegato a un runtime di orchestrazione.",
    )
