from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.access import owner_dependency
from core.approvals import ApprovalConflict, list_approvals, resolve_approval
from core.permissions import permission_manifest, validate_permission_configuration


router = APIRouter(
    prefix="/api/v1",
    tags=["Permissions"],
    dependencies=[Depends(owner_dependency("permissions"))],
)


class ApprovalDecision(BaseModel):
    approve: bool


@router.get("/permissions")
def permissions(actor: str = ""):
    return {
        "rules": permission_manifest(actor),
        "validation": validate_permission_configuration(),
    }


@router.get("/approvals")
def approvals(status: str = Query("pending"), limit: int = Query(100, ge=1, le=500)):
    try:
        return list_approvals(status, limit)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/approvals/{approval_id}/resolve")
def decide_approval(approval_id: str, decision: ApprovalDecision):
    try:
        return resolve_approval(approval_id, decision.approve)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error
    except ApprovalConflict as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
