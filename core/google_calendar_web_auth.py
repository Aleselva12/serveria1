"""Owner-initiated web OAuth, with short-lived single-use PKCE sessions.

The static callback page can load without an API session on Google's cross-site
redirect. It immediately removes the query, then uses the ordinary authenticated
POST endpoint. No public OAuth callback API or client-supplied redirect is needed.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from core import google_calendar as provider

TTL = 600


class SetupRequired(ValueError):
    pass


def _configuration():
    path = Path(os.getenv("CORA_GOOGLE_CALENDAR_WEB_CREDENTIALS_PATH", str(provider.TOKEN_PATH.parent / "web-credentials.json")))
    redirect = os.getenv("CORA_GOOGLE_CALENDAR_WEB_REDIRECT_URI", "").strip()
    if not path.is_file() or not redirect:
        raise SetupRequired("Configura una volta il client Google di tipo Applicazione web e l'indirizzo di ritorno. Il collegamento attuale resta valido.")
    config = json.loads(path.read_text())
    web = config.get("web", {})
    parsed = urlsplit(redirect)
    if (not web.get("client_id") or not web.get("client_secret")
        or web.get("auth_uri") != "https://accounts.google.com/o/oauth2/auth"
        or web.get("token_uri") != "https://oauth2.googleapis.com/token"
        or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
        or parsed.path != "/google-calendar-callback.html" or parsed.query or parsed.fragment
        or redirect not in web.get("redirect_uris", [])):
        raise SetupRequired("Client OAuth web o indirizzo di ritorno non valido: usa HTTPS e registra l'URL esatto /google-calendar-callback.html in Google Cloud.")
    return config, redirect


def configuration_status():
    try:
        _configuration()
        return {"available": True}
    except (ValueError, OSError):
        return {"available": False, "message": "Per il collegamento dal sito serve configurare una volta il client OAuth Google di tipo Applicazione web."}


def _directory():
    directory = provider.TOKEN_PATH.parent / "oauth-sessions"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def start():
    config, redirect = _configuration()
    state, key, verifier = (secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64))
    flow = Flow.from_client_config(config, provider.SCOPES, redirect_uri=redirect, code_verifier=verifier)
    url, _ = flow.authorization_url(state=state, access_type="offline", prompt="consent")
    directory = _directory()
    # Bounded lifetime for abandoned and consumed authorization sessions.
    now = time.time()
    for old in directory.glob("*.json*"):
        try:
            if old.stat().st_mtime < now - TTL:
                old.unlink(missing_ok=True)
        except FileNotFoundError:
            pass
    record = {"expires": now + TTL, "key_hash": hashlib.sha256(key.encode()).hexdigest(),
              "verifier": verifier, "client_id": config["web"]["client_id"], "redirect": redirect}
    fd = os.open(directory / (state + ".json"), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as target:
        json.dump(record, target)
    return {"url": url, "state": state, "completion_key": key, "expires_in": TTL}


def finish(*, state: str, completion_key: str, code: str = "", error: str = ""):
    if not state or len(state) > 128 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in state):
        raise ValueError("Sessione Google non valida. Riparti da Ricollega Google.")
    config, redirect = _configuration()
    path = _directory() / (state + ".json")
    try:
        record = json.loads(path.read_text())
    except FileNotFoundError:
        raise ValueError("Sessione Google scaduta o già utilizzata. Riparti da Ricollega Google.") from None
    if (record["expires"] < time.time() or record["client_id"] != config["web"]["client_id"]
        or record["redirect"] != redirect
        or not hmac.compare_digest(record["key_hash"], hashlib.sha256(completion_key.encode()).hexdigest())):
        raise ValueError("Sessione Google non valida o scaduta. Riparti da Ricollega Google.")
    # rename is atomic: only one callback can claim this session.
    claimed = path.with_suffix(".json.used")
    try:
        path.rename(claimed)
    except FileNotFoundError:
        raise ValueError("Sessione Google già utilizzata.") from None
    try:
        if error:
            return {"connected": False, "cancelled": True}
        if not code:
            raise ValueError("Google non ha restituito il codice di autorizzazione.")
        flow = Flow.from_client_config(config, provider.SCOPES, redirect_uri=redirect,
                                       state=state, code_verifier=record["verifier"])
        try:
            flow.fetch_token(code=code, timeout=20)
            credentials = flow.credentials
            if not credentials.refresh_token:
                raise ValueError("Missing refresh token")
            # Verify the new account before replacing the working token.
            build("calendar", "v3", credentials=credentials, cache_discovery=False).events().list(
                calendarId="primary", maxResults=1).execute()
        except Exception:
            raise ValueError("Autorizzazione Google non completata. Riparti da Ricollega Google; il collegamento precedente è stato conservato.") from None
        provider.save_credentials(credentials)
        return {"connected": True, "cancelled": False}
    finally:
        claimed.unlink(missing_ok=True)
