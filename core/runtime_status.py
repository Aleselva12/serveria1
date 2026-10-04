from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from core.component_bus import component_bus
from core.database import database_status
from core.models import get_model_name, get_ollama_base_url


def _ollama_online() -> bool:
    try:
        with urlopen(get_ollama_base_url().rstrip("/") + "/api/tags", timeout=1.0):
            return True
    except (URLError, TimeoutError, OSError):
        return False


def component_runtime_status() -> dict:
    ollama = _ollama_online()
    database = database_status()
    knowledge = Path(os.getenv("CORA_KNOWLEDGE_ROOT") or "./knowledge").expanduser()
    audio_root = Path(os.getenv("CORA_AUDIO_ROOT", "./audio")).expanduser()
    gmail_credentials = Path(os.getenv("CORA_GMAIL_CREDENTIALS_PATH", "./email_agent/credentials.json")).expanduser()
    gmail_token = Path(os.getenv("CORA_GMAIL_TOKEN_PATH", "./email_agent/token.json")).expanduser()

    components = {
        "supervisor": {
            "status": "ready" if ollama else "offline",
            "model": get_model_name("supervisor"),
            "checks": {"ollama": ollama},
        },
        "programmer_agent": {
            "status": "ready" if ollama else "offline",
            "model": get_model_name("programmer"),
            "checks": {"ollama": ollama, "source_writes": False},
        },
        "structure_agent": {
            "status": "ready" if ollama else "offline",
            "model": get_model_name("structure"),
            "checks": {"ollama": ollama},
        },
        "local_research_agent": {
            "status": "ready" if ollama and knowledge.exists() else "degraded" if ollama else "offline",
            "model": get_model_name("research"),
            "checks": {"ollama": ollama, "knowledge_root": knowledge.exists()},
        },
        "audio_agent": {
            "status": "ready" if ollama and importlib.util.find_spec("faster_whisper") else "degraded" if ollama else "offline",
            "model": get_model_name("audio"),
            "checks": {
                "ollama": ollama,
                "faster_whisper": importlib.util.find_spec("faster_whisper") is not None,
                "audio_root": audio_root.exists(),
            },
        },
        "email_quotes_agent": {
            "status": "ready" if ollama and (gmail_token.exists() or gmail_credentials.exists()) else "degraded" if ollama else "offline",
            "model": get_model_name("email"),
            "checks": {
                "ollama": ollama,
                "gmail_credentials": gmail_credentials.exists(),
                "gmail_token": gmail_token.exists(),
            },
        },
        "postgresql": {
            "status": "ready" if database.get("reachable") else "offline",
            "checks": database,
        },
    }
    live = component_bus.snapshot()
    for identifier, state in live.items():
        if identifier in components and state.get("status") == "busy":
            components[identifier]["status"] = "busy"
        components.setdefault(identifier, {"status": state.get("status", "unknown"), "checks": {}})
        components[identifier]["bus"] = state
    return {"components": components}
