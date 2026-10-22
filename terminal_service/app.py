"""Owner-only, password-authenticated SSH relay. Never executes a local shell."""
import asyncio
from collections import deque
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
import hmac
import json
import logging
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

import asyncssh
import anyio
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect

log = logging.getLogger("cora.terminal")
MAX_MESSAGE = 16384
IDLE_SECONDS = 300
MAX_SECONDS = 1800


@dataclass(frozen=True)
class Settings:
    owner: str
    proxy_secret: str
    origin: str
    host: str
    port: int
    username: str
    known_hosts: str

    @classmethod
    def from_env(cls):
        origin = os.environ.get("CORA_TERMINAL_ORIGIN", "").rstrip("/")
        url = urlsplit(origin)
        user = os.environ.get("CORA_TERMINAL_USER", "")
        owner = os.environ.get("CORA_TAILSCALE_LOGIN", "")
        secret = os.environ.get("CORA_TAILSCALE_PROXY_SECRET", "")
        known = os.environ.get("CORA_TERMINAL_KNOWN_HOSTS", "/config/known_hosts")
        if (os.environ.get("CORA_AUTH_MODE") != "tailscale" or not owner or len(secret) < 32
                or url.scheme != "https" or not url.hostname or not url.hostname.endswith(".ts.net")
                or url.port not in (None, 443) or url.username or url.password
                or url.path or url.query or url.fragment
                or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user) or user == "root"
                or not Path(known).is_file()):
            raise ValueError("Configurazione terminale incompleta: esegui deploy/terminal_setup.py sul server.")
        return cls(owner, secret, origin, os.environ.get("CORA_TERMINAL_HOST", "host.docker.internal"),
                   int(os.environ.get("CORA_TERMINAL_PORT", "22")), user, known)


def authorized(headers, config, *, require_origin):
    # The only proxy which can supply these headers is the configured Nginx bridge.
    supplied = headers.get("x-cora-proxy-secret", "")
    return (hmac.compare_digest(supplied.encode(), config.proxy_secret.encode())
            and headers.getlist("x-cora-tailscale-login") == [config.owner]
            and (headers.getlist("origin") == [config.origin] if require_origin
                 else not headers.get("origin") or headers.getlist("origin") == [config.origin]))


def frame(raw):
    if len(raw.encode()) > MAX_MESSAGE:
        raise ValueError("Messaggio troppo grande.")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Messaggio non valido.")
    return value


def size(value):
    cols, rows = value.get("cols", 80), value.get("rows", 24)
    if type(cols) is not int or type(rows) is not int or not 20 <= cols <= 400 or not 5 <= rows <= 150:
        raise ValueError("Dimensioni terminale non valide.")
    return cols, rows


def create_app(settings=None):
    sockets = set()
    attempts = deque()

    @asynccontextmanager
    async def lifespan(app):
        yield
        for ws in tuple(sockets):
            with suppress(Exception):
                await ws.close(code=1001)

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    def config():
        try:
            return settings or Settings.from_env()
        except (ValueError, OSError):
            raise HTTPException(503, "Terminale non configurato sul server.") from None

    @app.get("/terminal/status")
    def status(request: Request):
        cfg = config()
        if not authorized(request.headers, cfg, require_origin=False):
            raise HTTPException(403, "Apri Cora dal tuo indirizzo Tailscale HTTPS.")
        return {"username": cfg.username, "idle_seconds": IDLE_SECONDS, "max_seconds": MAX_SECONDS}

    @app.websocket("/terminal/connect")
    async def terminal(ws: WebSocket):
        try:
            cfg = config()
        except HTTPException:
            await ws.close(code=1008)
            return
        if not authorized(ws.headers, cfg, require_origin=True):
            await ws.close(code=1008)
            return
        # Single worker; reserve a slot before any await. Limit pending logins as well.
        now = time.monotonic()
        while attempts and now - attempts[0] >= 300:
            attempts.popleft()
        if len(attempts) >= 5 or len(sockets) >= 2:
            await ws.close(code=1008)
            return
        attempts.append(now)
        sockets.add(ws)
        connection = None
        tasks = []
        try:
            await ws.accept()
            auth = frame(await asyncio.wait_for(ws.receive_text(), 10))
            if (auth.get("type") != "auth" or set(auth) - {"type", "password", "cols", "rows"}
                    or not isinstance(auth.get("password"), str) or not 1 <= len(auth["password"]) <= 1024):
                raise ValueError("Autenticazione richiesta.")
            dimensions = size(auth)
            try:
                connection = await asyncio.wait_for(asyncssh.connect(
                    cfg.host, port=cfg.port, username=cfg.username, password=auth["password"],
                    known_hosts=cfg.known_hosts, client_keys=[], agent_path=None,
                    preferred_auth=["password"], config=None, disable_trivial_auth=True,
                    agent_forwarding=False, x11_forwarding=False,
                    connect_timeout=15, login_timeout=15), 20)
            finally:
                auth.clear()
            process = await asyncio.wait_for(connection.create_process(
                term_type="xterm-256color", term_size=dimensions, encoding="utf-8", errors="replace"), 10)
            await ws.send_json({"type": "ready"})
            log.info("Personal terminal connected")
            started = last_input = time.monotonic()

            async def output():
                while data := await process.stdout.read(4096):
                    await ws.send_json({"type": "output", "data": data})

            async def input_():
                nonlocal last_input
                while True:
                    data = frame(await ws.receive_text())
                    if data.get("type") == "input" and isinstance(data.get("data"), str):
                        if data["data"]:
                            last_input = time.monotonic()
                            process.stdin.write(data["data"])
                            await process.stdin.drain()
                    elif data.get("type") == "resize":
                        process.change_terminal_size(*size(data))
                    else:
                        raise ValueError("Messaggio non valido.")

            async def expiry():
                while True:
                    await asyncio.sleep(1)
                    now = time.monotonic()
                    if now - last_input >= IDLE_SECONDS or now - started >= MAX_SECONDS:
                        await ws.close(code=1000, reason="Sessione scaduta: accedi nuovamente.")
                        return

            tasks = [asyncio.create_task(coro()) for coro in (output, input_, expiry)]
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except asyncssh.PermissionDenied:
            with suppress(Exception):
                await ws.send_json({"type": "error", "message": "Password Debian non valida o accesso SSH con password non consentito."})
        except asyncssh.HostKeyNotVerifiable:
            with suppress(Exception):
                await ws.send_json({"type": "error", "message": "Identità SSH del server non verificata. Controlla la configurazione sul server."})
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception:
            # No exception strings, frames, password, terminal input/output, or SSH args in logs.
            with suppress(Exception):
                await ws.send_json({"type": "error", "message": "Connessione terminale interrotta o server SSH non disponibile."})
        finally:
            # Disconnect can cancel the ASGI request while SSH teardown is awaiting I/O.
            # Shield bounded cleanup so a vanished browser cannot leave a live shell.
            with anyio.CancelScope(shield=True):
                for task in tasks:
                    task.cancel()
                if connection:
                    connection.close()
                with suppress(Exception):
                    await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 5)
                if connection:
                    with suppress(Exception):
                        await asyncio.wait_for(connection.wait_closed(), 5)
                with suppress(Exception):
                    await asyncio.wait_for(ws.close(code=1000), 2)
                sockets.discard(ws)
                log.info("Personal terminal disconnected")

    return app


app = create_app()
