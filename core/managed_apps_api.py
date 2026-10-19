"""Owner-authenticated API bridge for fixed host-managed applications."""
from fastapi import APIRouter, HTTPException
from programmer_agent import releases

router=APIRouter(prefix="/api/v1/system/apps",tags=["Applicazioni server"])

@router.get("")
def status():
    try:
        return releases.request("GET","/managed-apps")
    except ValueError:
        return {"available":False,"apps":[],"reason":"Servizio host non disponibile o non configurato"}

@router.post("/{app_id}/{action}",status_code=202)
def action_request(app_id:str,action:str):
    if app_id!="magazzino-tele" or action not in {"install","update"}:
        raise HTTPException(404,"Applicazione o azione non autorizzata")
    try:
        return releases.request("POST",f"/managed-apps/{app_id}/{action}",{},timeout=30)
    except ValueError as exc:
        raise HTTPException(409,"Installazione o aggiornamento non disponibile: verificare lo stato del servizio host") from exc
