from fastapi import APIRouter
from core.permissions import permission_manifest,validate_permission_configuration

router = APIRouter(prefix="/api/v1",tags=["Permissions"])

@router.get("/permissions")
def permissions(actor: str = ""):
    return {"rules":permission_manifest(actor),"validation":validate_permission_configuration()}
