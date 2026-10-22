"""One-time Google Calendar OAuth helper for the Dockerized server.

From the user's computer open an SSH tunnel:
  ssh -L 8765:127.0.0.1:8765 ale@serverale

Then, in another SSH session on the server:
  python3 deploy/manage.py google-calendar-auth --login-hint you@example.com

The host helper launches the already-installed API image temporarily with host
networking and the persistent /state mount. The OAuth listener binds only to
127.0.0.1, so no Compose port is needed and nothing is exposed to LAN/Tailscale.
Open the printed Google URL in the computer browser. Google redirects to
http://localhost:8765/, which travels through SSH to the temporary listener.
"""
from __future__ import annotations

import argparse
import os
from wsgiref.simple_server import make_server
from wsgiref.util import request_uri

from google_auth_oauthlib.flow import InstalledAppFlow

from core.google_calendar import CREDENTIALS_PATH, SCOPES, TOKEN_PATH, verify_access


class CallbackApp:
    def __init__(self):
        self.last_request_uri = None

    def __call__(self, environ, start_response):
        self.last_request_uri = request_uri(environ)
        body = (
            "Google Calendar collegato a Cora. "
            "Puoi chiudere questa scheda e tornare al terminale."
        ).encode("utf-8")
        start_response(
            "200 OK",
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ],
        )
        return [body]


def authorize(port: int, login_hint: str = "", host: str = "127.0.0.1"):
    if not CREDENTIALS_PATH.is_file():
        raise FileNotFoundError(
            f"Credenziali Google non trovate: {CREDENTIALS_PATH}. "
            "Puoi riutilizzare il client OAuth già usato da Gmail."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    flow.redirect_uri = f"http://localhost:{port}/"
    params = {"access_type": "offline", "prompt": "consent"}
    if login_hint:
        params["login_hint"] = login_hint
    auth_url, _ = flow.authorization_url(**params)

    callback = CallbackApp()
    print("\nApri questo URL nel browser del computer con il tunnel SSH attivo:\n")
    print(auth_url)
    print("\nIn attesa dell'autorizzazione Google…")

    with make_server(host, port, callback) as server:
        server.handle_request()

    if not callback.last_request_uri:
        raise RuntimeError("Callback OAuth non ricevuto.")
    authorization_response = callback.last_request_uri
    # oauthlib requires https except for loopback redirect URIs; explicitly allow
    # the standards-defined localhost exception for this one-time flow.
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
    flow.fetch_token(authorization_response=authorization_response)
    creds = flow.credentials

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    os.chmod(TOKEN_PATH, 0o600)

    if not verify_access():
        raise RuntimeError("Autorizzazione ricevuta ma Calendar non verificabile.")
    print(f"\nGoogle Calendar collegato. Token salvato in {TOKEN_PATH}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--login-hint", default="")
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    authorize(args.port, args.login_hint, args.host)


if __name__ == "__main__":
    main()
