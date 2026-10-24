from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from urllib.error import URLError
from core.ollama_transport import urlopen, get_ollama_base_url

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
    from core.file_paths import library_workspace_status
    library = library_workspace_status()
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
            "status": "ready" if ollama and library['available'] else "degraded" if ollama else "offline",
            "model": get_model_name("research"),
            "checks": {"ollama": ollama, "knowledge_root": library['available'], "library": library},
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
    from core.agent_models import ROLES, binding, remote_ready
    from concurrent.futures import ThreadPoolExecutor
    assignments = {identifier: binding(role) for identifier, role in ROLES.items()}
    keys = {(s['machine_id'], s['model']) for s in assignments.values() if s and s['machine_id'] != 'local'}
    remote_checks = {}
    if keys:
        with ThreadPoolExecutor(max_workers=4) as probes:
            remote_checks = dict(zip(keys, probes.map(lambda key: remote_ready(*key), keys)))
    for identifier, role in ROLES.items():
        selected = assignments[identifier]
        if selected and selected['machine_id'] != 'local':
            key = (selected['machine_id'], selected['model'])
            ready = remote_checks[key]
            state = components[identifier]
            state['checks']['ollama'] = ready
            state['checks']['machine_id'] = selected['machine_id']
            extra_ready = all(bool(v) for k, v in state['checks'].items() if k in {'faster_whisper', 'knowledge_root', 'gmail_token'})
            if identifier == 'email_quotes_agent':
                extra_ready = state['checks']['gmail_token'] or state['checks']['gmail_credentials']
            state['status'] = 'offline' if not ready else 'ready' if extra_ready else 'degraded'
    live = component_bus.snapshot()
    for identifier, state in live.items():
        if identifier in components and state.get("status") == "busy":
            components[identifier]["status"] = "busy"
        components.setdefault(identifier, {"status": state.get("status", "unknown"), "checks": {}})
        components[identifier]["bus"] = state
    return {"components": components}
