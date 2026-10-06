"""Runtime profile guardrails for one codebase on DEV and SERVER."""
from __future__ import annotations

import json
import os
from urllib.parse import urlparse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def runtime_mode() -> str:
    mode = os.getenv("CORA_RUNTIME_MODE", "isolated").strip().lower()
    if mode not in {"isolated", "server"}:
        raise RuntimeError("CORA_RUNTIME_MODE deve essere 'isolated' oppure 'server'.")
    return mode


def _host(value: str) -> str:
    return (urlparse(value).hostname or "").lower()


def validate_runtime_profile() -> str:
    """Fail closed when DEV/isolated points at remote operational services."""
    mode = runtime_mode()
    if mode != "isolated":
        return mode

    remote = []
    for key in ("OLLAMA_BASE_URL", "CORA_DATABASE_URL", "CORA_UPDATER_URL",
                "CORA_SERVICE_IMMICH_URL", "CORA_SERVICE_NEXTCLOUD_URL", "CORA_SERVICE_N8N_URL"):
        value = os.getenv(key, "").strip()
        if value and _host(value) not in LOCAL_HOSTS:
            remote.append(key)

    roots = os.getenv("CORA_FILE_ROOTS", "").strip()
    if roots:
        try:
            entries = json.loads(roots)
        except ValueError as error:
            raise RuntimeError("CORA_FILE_ROOTS non è JSON valido.") from error
        for entry in entries:
            path = str(entry.get("path", "")).replace("\\", "/").lower()
            if path.startswith("/srv/nas/") or path.startswith("//"):
                remote.append("CORA_FILE_ROOTS")
                break

    if remote:
        raise RuntimeError(
            "Modalità isolated: riferimenti server/remoti vietati: " + ", ".join(sorted(set(remote)))
        )
    return mode
