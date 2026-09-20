from __future__ import annotations

import os

from langchain_ollama import ChatOllama


DEFAULT_MODEL = "gpt-oss:20b"
DEFAULT_BASE_URL = "http://localhost:11435"

ROLE_MODEL_ENV = {
    "supervisor": "CORA_MODEL_SUPERVISOR",
    "research": "CORA_MODEL_RESEARCH",
    "audio": "CORA_MODEL_AUDIO",
    "email": "CORA_MODEL_EMAIL",
}


def get_ollama_base_url() -> str:
    """Return the configured local Ollama endpoint."""
    return os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL)


def get_model_name(role: str = "default") -> str:
    """
    Resolve the model assigned to a role.

    A role-specific CORA_MODEL_* variable wins. OLLAMA_MODEL remains the
    backwards-compatible global fallback.
    """
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
    return ChatOllama(
        model=get_model_name(role),
        base_url=get_ollama_base_url(),
        temperature=temperature,
        **kwargs,
    )
