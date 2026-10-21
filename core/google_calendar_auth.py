"""One-time Google Calendar OAuth helper for a headless server.

Recommended from the user's computer:
  ssh -L 8765:127.0.0.1:8765 ale@serverale

Then, on the server:
  docker exec -it cora-api-1 python -m core.google_calendar_auth --port 8765 --login-hint you@example.com

Open the printed URL in the computer browser. Google's localhost callback
travels through the SSH tunnel to this process.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from core.google_calendar import CREDENTIALS_PATH, SCOPES, TOKEN_PATH, verify_access


def authorize(port: int, login_hint: str = ""):
    if not CREDENTIALS_PATH.is_file():
        raise FileNotFoundError(
            f"Credenziali Google non trovate: {CREDENTIALS_PATH}. "
            "Puoi riutilizzare il client OAuth già usato da Gmail."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    kwargs = {
        "host": "127.0.0.1",
        "port": port,
        "open_browser": False,
        "authorization_prompt_message": (
            "\nApri questo URL nel browser del computer collegato via tunnel SSH:\n{url}\n"
        ),
        "success_message": "Google Calendar collegato a Cora. Puoi chiudere questa scheda.",
        "access_type": "offline",
        "prompt": "consent",
    }
    if login_hint:
        kwargs["login_hint"] = login_hint
    creds = flow.run_local_server(**kwargs)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    os.chmod(TOKEN_PATH, 0o600)
    if not verify_access():
        raise RuntimeError("Autorizzazione ricevuta ma Calendar non verificabile.")
    print(f"Google Calendar collegato. Token salvato in {TOKEN_PATH}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--login-hint", default="")
    args = parser.parse_args()
    authorize(args.port, args.login_hint)


if __name__ == "__main__":
    main()
