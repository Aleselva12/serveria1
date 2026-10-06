from __future__ import annotations

import os
import json
from pathlib import Path
from urllib.request import urlopen, Request

from langchain_ollama import ChatOllama


DEFAULT_MODEL = "gpt-oss:20b"
DEFAULT_BASE_URL = "http://localhost:11435"

RUNTIME_SETTINGS_PATH = Path(os.getenv("CORA_RUNTIME_SETTINGS_PATH", "./data/runtime-settings.json"))

ROLE_MODEL_ENV = {
    "supervisor": "CORA_MODEL_SUPERVISOR",
    "research": "CORA_MODEL_RESEARCH",
    "audio": "CORA_MODEL_AUDIO",
    "email": "CORA_MODEL_EMAIL",
    "structure": "CORA_MODEL_STRUCTURE",
    "programmer": "CORA_MODEL_PROGRAMMER",
}


def get_ollama_base_url() -> str:
    """Return the configured local Ollama endpoint."""
    return os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL)


def get_model_keep_alive() -> str:
    """Keep the active Ollama model resident during an interactive session."""
    return os.getenv("CORA_MODEL_KEEP_ALIVE", "30m").strip() or "30m"


def _runtime_settings() -> dict:
    try:
        return json.loads(RUNTIME_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def save_runtime_model(model: str) -> dict:
    """Persist the operator-selected Ollama model for this Cora instance."""
    model = model.strip()
    available = {item["name"] for item in list_ollama_models()}
    if model not in available:
        raise ValueError("Il modello non risulta installato nell'istanza Ollama configurata.")
    data = _runtime_settings()
    data["model"] = model
    RUNTIME_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_SETTINGS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


def list_ollama_models() -> list[dict]:
    """Return models physically available in the configured Ollama instance."""
    with urlopen(get_ollama_base_url().rstrip("/") + "/api/tags", timeout=3) as response:
        payload = json.load(response)
    return [
        {"name": str(item.get("name", "")), "size": int(item.get("size", 0) or 0)}
        for item in payload.get("models", [])
        if item.get("name")
    ]


def get_model_name(role: str = "default") -> str:
    """
    Resolve the model assigned to a role.

    A role-specific CORA_MODEL_* variable wins. OLLAMA_MODEL remains the
    backwards-compatible global fallback.
    """
    runtime_model = str(_runtime_settings().get("model", "")).strip()
    if runtime_model:
        return runtime_model

    env_key = ROLE_MODEL_ENV.get(role)
    if env_key:
        configured = os.getenv(env_key, "").strip()
        if configured:
            return configured

    return os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)


def get_chat_model(
    role: str = "default",
    *,
    temperature: float = 0.0,
    **kwargs,
) -> ChatOllama:
    """Create the local chat model assigned to a Cora role."""
    from core.context_budget import limit_tokens
    kwargs.setdefault("num_ctx", limit_tokens())
    kwargs.setdefault("num_predict", int(os.getenv("CORA_OUTPUT_TOKENS", "1024")))
    kwargs.setdefault("keep_alive", get_model_keep_alive())
    kwargs.setdefault("client_kwargs", {"timeout": float(os.getenv("CORA_MODEL_TIMEOUT_SECONDS", "120")), "trust_env": False})
    kwargs.setdefault("metadata", {"cora_role": role})
    return ChatOllama(
        model=get_model_name(role),
        base_url=get_ollama_base_url(),
        temperature=temperature,
        **kwargs,
    )


def performance_configuration(target: str = "supervisor") -> dict:
    """Non-secret effective model/runtime settings stored with performance traces."""
    role_map = {
        "supervisor": "supervisor",
        "structure_agent": "structure",
        "local_research_agent": "research",
        "audio_agent": "audio",
        "email_quotes_agent": "email",
        "programmer_agent": "programmer",
    }
    role = role_map.get(target, target if target in ROLE_MODEL_ENV else "supervisor")
    return {
        "profile": os.getenv("CORA_PERFORMANCE_PROFILE", "default"),
        "target": target,
        "role": role,
        "model": get_model_name(role),
        "models": {name: get_model_name(name) for name in ROLE_MODEL_ENV},
        "ollama_base_url": get_ollama_base_url(),
        "keep_alive": get_model_keep_alive(),
        "context_tokens": int(os.getenv("CORA_CONTEXT_TOKENS", "16384")),
        "output_tokens": int(os.getenv("CORA_OUTPUT_TOKENS", "1024")),
        "model_timeout_seconds": float(os.getenv("CORA_MODEL_TIMEOUT_SECONDS", "120")),
        "run_timeout_seconds": float(os.getenv("CORA_RUN_TIMEOUT_SECONDS", "300")),
        "queue_size": int(os.getenv("CORA_RUN_QUEUE_SIZE", "8")),
        "db_pool_size": int(os.getenv("CORA_DB_POOL_SIZE", "4")),
        "hardware_label": os.getenv("CORA_PERFORMANCE_HARDWARE_LABEL", "").strip(),
        "gpu_label": os.getenv("CORA_PERFORMANCE_GPU_LABEL", "").strip(),
    }
