"""Periodic, NON-DESTRUCTIVE project preflights.

Never write documents, trigger model inference, send mail, mutate calendar data,
run backups or restart services. These checks do not prove end-to-end workflows.
The snapshot is process-local and resets after a backend restart.
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["Project checks"])
_LOCK = threading.RLock()
_STOP = threading.Event()
_THREAD: threading.Thread | None = None
_INTERVAL = 300
_LAST: dict | None = None

CHECKS = {
    "database": "Connessione PostgreSQL",
    "library": "Lettura Libreria IA",
    "audio": "Prerequisiti motore Audio",
    "ollama": "Catalogo modelli Ollama",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _database() -> tuple[str, str]:
    """SELECT 1 without invoking schema setup/migrations."""
    from core.database import DATABASE_URL
    if not DATABASE_URL:
        return "unknown", "Connessione database non configurata"
    import psycopg
    with psycopg.connect(DATABASE_URL, connect_timeout=3, options="-c statement_timeout=5000") as connection:
        if connection.execute("SELECT 1").fetchone()[0] != 1:
            return "fail", "PostgreSQL non risponde alla query di lettura"
    return "pass", "SELECT 1 eseguita; dati e schema applicativo non collaudati"


def _library() -> tuple[str, str]:
    from core.file_paths import knowledge_root
    root = knowledge_root()
    if not root.exists() or not root.is_dir():
        return "fail", "Percorso Libreria IA non disponibile"
    with os.scandir(root) as iterator:
        next(iterator, None)
    return "pass", "Directory leggibile; upload, permessi di scrittura e ripristino non provati"


def _audio() -> tuple[str, str]:
    from core.audio_api import audio_status
    result = audio_status()
    if result.get("ready"):
        return "pass", "Motore dichiarato pronto; trascrizione reale non eseguita"
    return "fail", "Motore Audio non pronto; verifica dipendenze e modello locale"


def _ollama() -> tuple[str, str]:
    from core.ollama_transport import get_ollama_base_url, urlopen
    with urlopen(get_ollama_base_url() + "/api/tags", timeout=2) as response:
        if not 200 <= response.status < 300:
            return "fail", "Catalogo Ollama non raggiungibile"
    return "pass", "Catalogo raggiungibile; nessuna inferenza o GPU verificata"


_PROBES = {"database": _database, "library": _library, "audio": _audio, "ollama": _ollama}


def run_once() -> dict:
    """Each check is independent. Store one immutable snapshot atomically."""
    global _LAST
    checks = []
    for key, probe in _PROBES.items():
        try:
            status, detail = probe()
        except Exception:
            status, detail = "fail", "Controllo non riuscito; esaminare la diagnostica del servizio"
        checks.append({"id": key, "label": CHECKS[key], "status": status,
                       "detail": detail, "checkedAt": _now()})
    snap = {"checkedAt": _now(), "intervalSeconds": _INTERVAL,
            "scope": "preflight_only", "checks": checks}
    with _LOCK:
        _LAST = snap
    return snap


def snapshot() -> dict:
    with _LOCK:
        if _LAST is None:
            return {"checkedAt": None, "intervalSeconds": _INTERVAL,
                    "scope": "preflight_only", "checks": []}
        return {
            "checkedAt": _LAST["checkedAt"],
            "intervalSeconds": _INTERVAL,
            "scope": "preflight_only",
            "checks": [dict(x) for x in _LAST["checks"]],
        }


def _loop() -> None:
    run_once()
    while not _STOP.wait(_INTERVAL):
        run_once()


def start() -> None:
    global _THREAD
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return
        _STOP.clear()
        _THREAD = threading.Thread(target=_loop, name="cora-project-preflight", daemon=True)
        _THREAD.start()


def stop() -> None:
    with _LOCK:
        _STOP.set()
        worker = _THREAD
    if worker and worker.is_alive():
        worker.join(timeout=3)


@router.get("/project/checks")
def current_checks():
    return snapshot()
