"""Owner login. Provision credentials from the host, never from a public setup API."""
import hashlib
import hmac
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from getpass import getpass
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from core.database import db_connection

COOKIE = "cora_session"
router = APIRouter(prefix="/auth", tags=["Accesso"])
_attempts = {}
_lock = threading.Lock()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ":" + digest


def verify_password(password, stored):
    try:
        return hmac.compare_digest(password_hash(password, stored.split(":")[0]), stored)
    except (ValueError, TypeError):
        return False


_DUMMY_HASH = password_hash("unused-dummy-credential")

def provision(username, password):
    if len(password) < 12:
        raise ValueError("Usa una password di almeno 12 caratteri.")
    with db_connection() as conn:
        existing = conn.execute("SELECT id FROM app_users WHERE username=%s", (username,)).fetchone()
        if not existing and conn.execute("SELECT id FROM app_users LIMIT 1").fetchone():
            raise ValueError("Questa versione supporta un unico proprietario.")
        row = conn.execute("""INSERT INTO app_users (id,username,password_hash)
            VALUES (%s,%s,%s) ON CONFLICT(username) DO UPDATE SET password_hash=EXCLUDED.password_hash
            RETURNING id""", (uuid4(), username, password_hash(password))).fetchone()
        conn.execute("DELETE FROM app_sessions WHERE user_id=%s", (row["id"],))
        conn.commit()


def session_user(token):
    if not token:
        return None
    with db_connection() as conn:
        return conn.execute("""SELECT u.id,u.username FROM app_sessions s JOIN app_users u ON u.id=s.user_id
            WHERE s.token_hash=%s AND s.expires_at>NOW()""", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()


def check_browser_write(request):
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    # Required custom header prevents ambient-cookie requests from foreign forms.
    if request.headers.get("x-cora-client") != "ui":
        raise HTTPException(403, "Header X-Cora-Client richiesto.")
    origin = request.headers.get("origin")
    allowed = {x.strip().rstrip("/") for x in os.getenv("CORA_UI_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")}
    if origin and origin.rstrip("/") not in allowed:
        raise HTTPException(403, "Origine non autorizzata.")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        try:
            check_browser_write(request)
            if request.url.path not in {"/auth/login", "/auth/status"}:
                from starlette.concurrency import run_in_threadpool
                user = await run_in_threadpool(session_user, request.cookies.get(COOKIE))
                if not user:
                    raise HTTPException(401, "Accedi a Cora.")
                request.state.user = user
        except HTTPException as error:
            return JSONResponse({"detail": error.detail}, status_code=error.status_code)
        except Exception:
            return JSONResponse({"detail": "Accesso non disponibile: verifica PostgreSQL."}, status_code=503)
        return await call_next(request)


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1024)


@router.get("/status")
def status(request: Request):
    user = session_user(request.cookies.get(COOKIE))
    return {"authenticated": bool(user), "username": user["username"] if user else None}


@router.post("/login")
def login(data: Login, request: Request, response: Response):
    host = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _lock:
        for key in list(_attempts):
            _attempts[key] = [t for t in _attempts[key] if now - t < 300]
            if not _attempts[key]:
                del _attempts[key]
        attempts = _attempts.setdefault(host, [])
        if len(attempts) >= 5 or sum(map(len, _attempts.values())) >= 100:
            raise HTTPException(429, "Troppi tentativi. Riprova fra cinque minuti.")
        attempts.append(now)
    with db_connection() as conn:
        row = conn.execute("SELECT * FROM app_users WHERE username=%s", (data.username,)).fetchone()
        # Equalize expensive hashing for unknown usernames too.
        valid = verify_password(data.password, row["password_hash"] if row else _DUMMY_HASH)
        if not row or not valid:
            raise HTTPException(401, "Credenziali non valide.")
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=7)
        conn.execute("DELETE FROM app_sessions WHERE expires_at<=NOW()")
        conn.execute("INSERT INTO app_sessions (token_hash,user_id,expires_at) VALUES (%s,%s,%s)",
                     (hashlib.sha256(token.encode()).hexdigest(), row["id"], expires))
        conn.commit()
    with _lock: _attempts.pop(host, None)
    response.set_cookie(COOKIE, token, max_age=604800, httponly=True, samesite="strict",
                        secure=os.getenv("CORA_COOKIE_SECURE", "false").lower() == "true", path="/")
    return {"authenticated": True, "username": row["username"]}


@router.post("/logout")
def logout(request: Request, response: Response, all_sessions: bool = False):
    with db_connection() as conn:
        if all_sessions:
            conn.execute("DELETE FROM app_sessions WHERE user_id=%s", (request.state.user["id"],))
        else:
            conn.execute("DELETE FROM app_sessions WHERE token_hash=%s", (hashlib.sha256(request.cookies[COOKIE].encode()).hexdigest(),))
        conn.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"authenticated": False}


if __name__ == "__main__":
    username = input("Nome proprietario: ").strip()
    if not username or len(username) > 100:
        raise ValueError("Nome non valido.")
    password = getpass("Password (almeno 12 caratteri): ")
    if password != getpass("Ripeti password: "):
        raise ValueError("Password diverse.")
    provision(username, password)
    print("Proprietario configurato. Le sessioni precedenti sono revocate.")
