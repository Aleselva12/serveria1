"""Install the small curated default Ollama set without touching user-installed models."""
from __future__ import annotations

import json
import threading
from urllib.request import Request

from core.ollama_transport import get_ollama_base_url, urlopen
from core.models import list_ollama_models

DEFAULT_MODELS = (
    {"name": "qwen3:0.6b", "role": "Controlli leggeri / larva"},
    {"name": "qwen3:4b", "role": "Router specializzato shadow"},
    {"name": "qwen3:8b", "role": "Orchestratore principale leggero"},
    {"name": "nomic-embed-text:latest", "role": "Embedding e retrieval"},
)

_lock = threading.RLock()
_state = {
    "running": False,
    "current_model": None,
    "completed": [],
    "failed": [],
    "last_error": None,
}

def _installed_names() -> set[str]:
    return {str(row.get("name", "")) for row in list_ollama_models() if row.get("name")}

def status() -> dict:
    installed = _installed_names()
    with _lock:
        state = {
            "running": bool(_state["running"]),
            "current_model": _state["current_model"],
            "completed": list(_state["completed"]),
            "failed": list(_state["failed"]),
            "last_error": _state["last_error"],
        }
    models = [
        {**row, "installed": row["name"] in installed}
        for row in DEFAULT_MODELS
    ]
    return {
        **state,
        "models": models,
        "missing": [row["name"] for row in models if not row["installed"]],
        "note": "I modelli già presenti non vengono modificati o eliminati. Il download non cambia il modello attivo.",
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

def _worker(models: list[str]) -> None:
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
            _state["current_model"] = None

def start_download() -> dict:
    installed = _installed_names()
    missing = [row["name"] for row in DEFAULT_MODELS if row["name"] not in installed]
    with _lock:
        if _state["running"]:
            return status()
        _state["completed"] = []
        _state["failed"] = []
        _state["last_error"] = None
        if not missing:
            return status()
        _state["running"] = True
        _state["current_model"] = missing[0]
    threading.Thread(target=_worker, args=(missing,), daemon=True, name="cora-default-models").start()
    return status()
