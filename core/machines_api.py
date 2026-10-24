"""Machine inventory and opt-in worker connectivity, not remote execution.

Inventory uses Tailscale read-only OAuth when configured; the worker probe contacts
only an explicitly registered *.ts.net hostname and a fixed /health endpoint.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/api/v1/machines", tags=["Macchine"])
_registry_lock = threading.RLock()
_FQDN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+\.ts\.net$")


class MachineRegistration(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    fqdn: str = Field(min_length=7, max_length=253)

    @field_validator("fqdn")
    @classmethod
    def valid_tailnet_hostname(cls, value: str) -> str:
        name = value.strip().lower().rstrip(".")
        if not _FQDN.fullmatch(name):
            raise ValueError("Usa il nome Tailscale completo, ad esempio desktop.tailnet.ts.net")
        configured = os.getenv("CORA_TAILSCALE_DNS_SUFFIX", "").strip().lower().lstrip(".")
        if configured and not name.endswith("." + configured):
            raise ValueError("Macchina esterna alla tailnet configurata")
        return name


def _path() -> Path:
    return Path(os.getenv("CORA_MACHINES_REGISTRY_FILE", "/state/machines.json"))


def _read() -> list[dict]:
    path = _path()
    if not path.is_file():
        return []
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(parsed, list):
            raise ValueError("Invalid registry")
        return [item for item in parsed if isinstance(item, dict)]
    except (ValueError, OSError) as exc:
        raise HTTPException(503, "Inventario macchine non leggibile; verifica il file di stato.") from exc


def _write(items: list[dict]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".machines-", suffix=".tmp", dir=path.parent)
    try:
        os.chmod(name, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(items, file, indent=2, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _tailscale_devices() -> tuple[list[dict], str | None, bool]:
    tailnet = os.getenv("CORA_TAILSCALE_TAILNET", "").strip()
    client = os.getenv("CORA_TAILSCALE_OAUTH_CLIENT_ID", "").strip()
    secret = os.getenv("CORA_TAILSCALE_OAUTH_CLIENT_SECRET", "").strip()
    if not all((tailnet, client, secret)):
        return [], None, False
    try:
        form = urlencode({"grant_type": "client_credentials", "client_id": client,
                          "client_secret": secret, "scope": "devices:core:read"}).encode()
        token_request = Request("https://api.tailscale.com/api/v2/oauth/token",
                                data=form, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urlopen(token_request, timeout=5) as response:
            access_token = json.load(response)["access_token"]
        url = "https://api.tailscale.com/api/v2/tailnet/" + quote(tailnet, safe="") + "/devices"
        inventory_request = Request(url, headers={"Authorization": "Bearer " + access_token})
        with urlopen(inventory_request, timeout=5) as response:
            payload = json.load(response)
        items = payload.get("devices", [])
        return [
            {"id": str(d.get("id") or ""), "name": str(d.get("name") or d.get("hostname") or ""),
             "fqdn": str(d.get("name") or "").lower().rstrip("."),
             "online": d.get("online") if isinstance(d.get("online"), bool) else None}
            for d in items[:200] if isinstance(d, dict)
        ], None, True
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
        return [], "Inventario Tailscale non raggiungibile: controllare OAuth e connessione.", True


def _probe(fqdn: str) -> tuple[bool, list[str]]:
    # Do not accept arbitrary URLs or private-network hosts from user input.
    if not _FQDN.fullmatch(fqdn):
        return False, []
    try:
        req = Request("https://" + fqdn + "/health", headers={"Accept": "application/json"})
        with urlopen(req, timeout=2) as response:
            if response.status != 200:
                return False, []
            body = json.load(response)
        if body.get("protocol") != "cora-worker-v1" or body.get("execution_enabled") is not False:
            return False, []
        capabilities = body.get("capabilities")
        return True, capabilities if isinstance(capabilities, list) and all(isinstance(c, str) for c in capabilities) else []
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError):
        return False, []


@router.get("")
def list_machines():
    with _registry_lock:
        registered = _read()
    discovered, discovery_error, configured = _tailscale_devices()
    known = {d["fqdn"]: d for d in discovered if d["fqdn"]}
    nodes = [{
        "id": "cora-server", "name": "Server Cora / Debian", "fqdn": "",
        "type": "coordinator", "online": True, "worker_ready": False,
        "capabilities": [], "registered": True,
    }]
    seen = set()
    for item in registered:
        fqdn = str(item.get("fqdn", ""))
        if not _FQDN.fullmatch(fqdn):
            continue
        active, capabilities = _probe(fqdn)
        entry = known.get(fqdn)
        nodes.append({
            "id": str(item.get("id")), "name": str(item.get("name")),
            "fqdn": fqdn, "type": "worker", "online": entry["online"] if entry else None,
            "worker_ready": active, "capabilities": capabilities, "registered": True,
        })
        seen.add(fqdn)
    for item in discovered:
        if item["fqdn"] in seen:
            continue
        nodes.append({
            "id": item["id"], "name": item["name"], "fqdn": item["fqdn"],
            "type": "tailnet_device", "online": item["online"], "worker_ready": False,
            "capabilities": [], "registered": False,
        })
    return {"machines": nodes, "tailscale_discovery_configured": configured,
            "tailscale_error": discovery_error, "execution_enabled": False}


@router.post("", status_code=201)
def add_machine(body: MachineRegistration):
    with _registry_lock:
        items = _read()
        if any(i.get("fqdn") == body.fqdn for i in items):
            raise HTTPException(409, "Macchina già registrata.")
        if len(items) >= 20:
            raise HTTPException(409, "Numero massimo di worker raggiunto.")
        item = {"id": str(uuid4()), "name": body.name.strip(), "fqdn": body.fqdn}
        _write([*items, item])
    return item


@router.delete("/{machine_id}")
def delete_machine(machine_id: str):
    with _registry_lock:
        items = _read()
        remaining = [i for i in items if i.get("id") != machine_id]
        if len(items) == len(remaining):
            raise HTTPException(404, "Macchina non trovata.")
        _write(remaining)
    return {"removed": True}
