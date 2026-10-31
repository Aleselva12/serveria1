"""Curated Ollama model packs. Downloads are non-destructive and never change assignments."""
from __future__ import annotations

import json
import threading
from urllib.request import Request

from core.ollama_transport import get_ollama_base_url, urlopen
from core.models import list_ollama_models

MODEL_PACKS = {
    "base": (
        {"name": "qwen3:0.6b", "role": "Controlli leggeri / larva"},
        {"name": "qwen3:4b", "role": "Router specializzato shadow"},
        {"name": "qwen3:8b", "role": "Orchestratore principale leggero"},
        {"name": "nomic-embed-text:latest", "role": "Embedding e retrieval"},
    ),
    "now": (
        {"name": "qwen2.5-coder:7b", "role": "Codice e supporto al Programmatore"},
        {"name": "gemma3:4b", "role": "Visione e comprensione immagini/documenti"},
        {"name": "deepseek-r1:8b", "role": "Reasoning alternativo / verifica"},
    ),
    "future": (
        {"name": "qwen3-coder:30b", "role": "Programmatore agentico futuro / repository grandi"},
        {"name": "gemma3:12b", "role": "Visione più forte e documenti multimodali"},
        {"name": "deepseek-r1:14b", "role": "Reasoning futuro più capace"},
    ),
}
DEFAULT_MODELS = MODEL_PACKS["base"]

_lock = threading.RLock()
_state = {
    "running": False,
    "pack": None,
    "current_model": None,
    "completed": [],
    "failed": [],
    "last_error": None,
}

def _installed_names() -> set[str]:
    return {str(row.get("name", "")) for row in list_ollama_models() if row.get("name")}

def _pack_rows(installed: set[str]) -> dict:
    return {
        pack: [{**row, "installed": row["name"] in installed} for row in rows]
        for pack, rows in MODEL_PACKS.items()
    }

def status() -> dict:
    installed = _installed_names()
    packs = _pack_rows(installed)
    with _lock:
        state = {
            "running": bool(_state["running"]),
            "pack": _state["pack"],
            "current_model": _state["current_model"],
            "completed": list(_state["completed"]),
            "failed": list(_state["failed"]),
            "last_error": _state["last_error"],
        }
    return {
        **state,
        "packs": packs,
        "missing": {
            pack: [row["name"] for row in rows if not row["installed"]]
            for pack, rows in packs.items()
        },
        "note": "I download sono solo installazioni locali: nessun modello già presente viene eliminato, nessun agente viene riassegnato e il modello attivo non cambia.",
    }

def _pull(model: str) -> None:
    request = Request(
        get_ollama_base_url().rstrip("/") + "/api/pull",
        data=json.dumps({"model": model, "stream": True}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last = ""
    with urlopen(request, timeout=None) as response:
        for line in response:
            row = json.loads(line)
            if row.get("error"):
                raise RuntimeError(str(row["error"]))
            if row.get("status"):
                last = str(row["status"])
    if last != "success":
        raise RuntimeError("Ollama non ha confermato il completamento del download.")

def _worker(pack: str, models: list[str]) -> None:
    try:
        for model in models:
            with _lock:
                _state["current_model"] = model
            try:
                _pull(model)
                with _lock:
                    _state["completed"].append(model)
            except Exception as error:
                with _lock:
                    _state["failed"].append(model)
                    _state["last_error"] = type(error).__name__
                break
    finally:
        with _lock:
            _state["running"] = False
            _state["pack"] = None
            _state["current_model"] = None

def start_download(pack: str = "base") -> dict:
    if pack not in MODEL_PACKS:
        raise ValueError("Pacchetto modelli sconosciuto.")
    installed = _installed_names()
    missing = [row["name"] for row in MODEL_PACKS[pack] if row["name"] not in installed]
    with _lock:
        if _state["running"]:
            return status()
        _state["completed"] = []
        _state["failed"] = []
        _state["last_error"] = None
        if not missing:
            return status()
        _state["running"] = True
        _state["pack"] = pack
        _state["current_model"] = missing[0]
    threading.Thread(target=_worker, args=(pack, missing), daemon=True, name=f"cora-models-{pack}").start()
    return status()
