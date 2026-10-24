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
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Literal

router = APIRouter(prefix="/api/v1/machines", tags=["Macchine"])
_registry_lock = threading.RLock()
PROFILES = ("heavy", "medium", "light")
DEFAULT_MODELS = {
    "heavy": "gpt-oss:20b",
    "medium": "qwen3:8b-q8_0",
    "light": "qwen3:4b-q8_0",
}
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,179}$")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _settings(machine):
    saved = machine.get("profiles") if isinstance(machine.get("profiles"), dict) else {}
    return {
        "enabled": machine.get("enabled") is True,
        "active_profile": machine.get("active_profile") if machine.get("active_profile") in PROFILES else "heavy",
        "profiles": {profile: saved.get(profile) if isinstance(saved.get(profile), str)
                     else model for profile, model in DEFAULT_MODELS.items()},
    }


class WorkerSettings(BaseModel):
    enabled: bool
    active_profile: Literal["heavy", "medium", "light"]
    profiles: dict[str, str]

    @field_validator("profiles")
    @classmethod
    def profiles_valid(cls, value):
        if set(value) != set(PROFILES) or not all(_MODEL.fullmatch(v) for v in value.values()):
            raise ValueError("Sono richiesti tre modelli con nomi Ollama validi.")
        return value


class InferencePrompt(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)

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
        with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=2) as response:
            if response.status != 200:
                return False, []
            raw = response.read(8193)
            if len(raw) > 8192:
                return False, []
            body = json.loads(raw)
        if not isinstance(body, dict):
            return False, []
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
            **_settings(item),
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
            "tailscale_error": discovery_error, "execution_enabled": any(_settings(i)["enabled"] for i in registered)}


@router.post("", status_code=201)
def add_machine(body: MachineRegistration):
    with _registry_lock:
        items = _read()
        if any(i.get("fqdn") == body.fqdn for i in items):
            raise HTTPException(409, "Macchina già registrata.")
        if len(items) >= 20:
            raise HTTPException(409, "Numero massimo di worker raggiunto.")
        item = {"id": str(uuid4()), "name": body.name.strip(), "fqdn": body.fqdn,
                **_settings({})}
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


def _find(machine_id: str):
    with _registry_lock:
        for machine in _read():
            if machine.get("id") == machine_id:
                return machine
    raise HTTPException(404, "Worker non registrato.")


def _worker_call(machine: dict, path: str, payload: dict | None = None, timeout: int = 7) -> dict:
    token = os.getenv("CORA_WORKER_SHARED_TOKEN", "")
    if len(token) < 32:
        raise HTTPException(503, "Configura CORA_WORKER_SHARED_TOKEN nel backend e CORA_WORKER_TOKEN sul desktop.")
    try:
        fqdn = MachineRegistration(name=machine["name"], fqdn=machine["fqdn"]).fqdn
    except (ValueError, KeyError) as error:
        raise HTTPException(503, "Configurazione worker non valida per la tailnet corrente.") from error
    suffix = os.getenv("CORA_TAILSCALE_DNS_SUFFIX", "").strip().lower().lstrip(".")
    if not suffix or not suffix.endswith(".ts.net") or not fqdn.endswith("." + suffix):
        raise HTTPException(503, "Imposta CORA_TAILSCALE_DNS_SUFFIX prima di collegare worker remoti.")
    raw = None if payload is None else json.dumps(payload).encode()
    req = Request("https://" + fqdn + path,
                  data=raw,
                  headers={"X-Cora-Worker-Token": token, "Content-Type": "application/json",
                           "Accept": "application/json"})
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as response:
            body = response.read(1_000_001)
        if len(body) > 1_000_000:
            raise ValueError("Risposta troppo grande")
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise ValueError("Risposta non valida")
        return parsed
    except HTTPError as error:
        if error.code in (403, 401):
            raise HTTPException(503, "Il token di Cora non corrisponde a quello del worker.") from error
        raise HTTPException(503, "Il worker ha restituito HTTP " + str(error.code)) from error
    except (URLError, TimeoutError, OSError, ValueError) as error:
        raise HTTPException(503, "Worker o Ollama non raggiungibile.") from error


@router.get("/{machine_id}/models")
def models(machine_id: str):
    machine = _find(machine_id)
    result = _worker_call(machine, "/models")
    return {**result, "settings": _settings(machine)}


@router.put("/{machine_id}/settings")
def save_settings(machine_id: str, body: WorkerSettings):
    # Only the owner-authenticated HTTP API can change model selection.
    # No LangGraph tools or agent-facing endpoints are registered.
    with _registry_lock:
        machines = _read()
        for item in machines:
            if item.get("id") == machine_id:
                item.update(body.model_dump())
                _write(machines)
                return _settings(item)
    raise HTTPException(404, "Worker non registrato.")


@router.post("/{machine_id}/generate")
def generate(machine_id: str, body: InferencePrompt):
    machine = _find(machine_id)
    settings = _settings(machine)
    if not settings["enabled"]:
        raise HTTPException(409, "Worker disattivato manualmente.")
    model = settings["profiles"][settings["active_profile"]]
    # No caller-supplied model identifier and no model-switch tool for agents.
    available = _worker_call(machine, "/models").get("models", [])
    if model not in {row.get("name") for row in available if isinstance(row, dict)}:
        raise HTTPException(409, "Il modello selezionato non è installato sul desktop.")
    return _worker_call(machine, "/generate", {"model": model, "prompt": body.prompt}, timeout=315)


@router.post("/{machine_id}/test")
def test_worker_inference(machine_id: str):
    return generate(machine_id, InferencePrompt(prompt="Scrivi esattamente la parola: CORA_WORKER_OK"))
