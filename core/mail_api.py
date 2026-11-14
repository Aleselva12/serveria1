"""Owner-only Mail API; deliberately no send, modify or scheduling endpoint."""
import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from core.access import require_owner
from core import mail, mail_web_auth
from core.calendar_api import GoogleAuthFinish

def mail_owner(request: Request, response: Response):
    require_owner(request, "mail")
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/api/v1/mail", tags=["Mail"], dependencies=[Depends(mail_owner)])
Selection = Literal["a", "b", "all"]
Scope = Literal["inbox", "unread", "yesterday"]


def safe(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except Exception:
        raise HTTPException(503, "Mail non disponibile: verifica collegamento Google e configurazione server.") from None


@router.get("/accounts")
def accounts():
    return {"accounts": [{"id": key, "email": email, "connected": mail.token_path(key).is_file()} for key, email in mail.ACCOUNTS.items()], "webAuth": mail_web_auth.configuration_status()}


@router.post("/accounts/{account}/auth/start")
def auth_start(account: Literal["a", "b"]):
    return safe(mail_web_auth.start, account)


@router.post("/google/auth/finish")
def auth_finish(body: GoogleAuthFinish):
    return safe(mail_web_auth.finish, **body.model_dump())


@router.get("/messages")
def messages(selection: Selection = "all", scope: Scope = "inbox", cursors: str = Query(default="{}", max_length=8192)):
    try:
        pages = json.loads(cursors)
        if not isinstance(pages, dict) or any(k not in mail.ACCOUNTS or not isinstance(v, str) or len(v)>2048 for k,v in pages.items()):
            raise ValueError()
    except ValueError:
        raise HTTPException(422, "Paginazione non valida") from None
    return safe(mail.messages, selection, scope, pages)


@router.get("/accounts/{account}/messages/{message_id}")
def detail(account: Literal["a", "b"], message_id: str):
    return safe(mail.detail, account, message_id)


class Summary(BaseModel):
    selection: Selection = "all"
    scope: Scope = "yesterday"


@router.post("/summary")
def summary(body: Summary):
    return safe(mail.summarize, body.selection, body.scope)


@router.get("/automation-template")
def automation_template(selection: Selection = "all"):
    return mail.automation_template(selection)
