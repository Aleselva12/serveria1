"""Read-only orchestration API.

Kept separate from the runtime lifecycle router so orchestration diagnostics
cannot depend on runtime router import order or mutate execution state.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["Orchestration"])


@router.get("/runtime/capabilities")
def operational_capabilities():
    from core.operational_capabilities import operational_registry
    return operational_registry()


@router.get("/runtime/coordinator")
def coordinator_snapshot():
    from core.system_coordinator import snapshot
    return snapshot()


@router.get("/runtime/context-contracts")
def context_contracts():
    from core.context_contracts import ContextRequest, ContextPacket
    return {
        "version": 1,
        "request": ContextRequest.model_json_schema(),
        "packet": ContextPacket.model_json_schema(),
        "principles": {
            "permission_bound": True,
            "progressive_expansion": True,
            "literal_wins_conflict": True,
            "newer_wins_when_equally_authoritative": True,
            "writes_memory": False,
        },
    }
