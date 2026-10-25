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
from core.health_catalog import CATALOG
from core import project_contracts

router = APIRouter(prefix="/api/v1", tags=["Project checks"])
_LOCK = threading.RLock()
_STOP = threading.Event()
_THREAD: threading.Thread | None = None
_INTERVAL = 300
_LAST: dict | None = None

CHECKS = {key: item["title"] for key,item in CATALOG.items() if item["automated"]}

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



def _word_sample() -> tuple[str, str]:
    """Run a REAL append-only Word transformation on in-memory synthetic data."""
    from io import BytesIO
    from docx import Document
    from core.commercial_word import parse, propose_append

    document = Document()
    for line in ("LIDO TEST", "Interlocutore prova", "21/10/2026", "Nota originale",
                 "---------------------------------------------------------",
                 "HOTEL SECONDO", "Referente", "21/10/2026", "Altro contenuto",
                 "---------------------------------------------------------"):
        document.add_paragraph(line)
    stream = BytesIO()
    document.save(stream)
    source = stream.getvalue()
    blocks = parse(source)
    if len(blocks) != 2:
        return "fail", "Segmentazione Word sintetico non riuscita"
    candidate = propose_append(source, blocks[0], "25/10/2026", "Nuova nota di prova")
    old = [p.text for p in Document(BytesIO(source)).paragraphs]
    new = [p.text for p in Document(BytesIO(candidate)).paragraphs]
    if new != old[:4] + ["25/10/2026", "Nuova nota di prova"] + old[4:]:
        return "fail", "Aggiunta Word sintetica non preserva i paragrafi"
    return "pass", "Aggiunta append-only riuscita in memoria; file reali non testati"


_PROBES = {
    "database": _database, "library": _library, "audio": _audio,
    "ollama": _ollama, "word_sample": _word_sample,
    "chat_contract": project_contracts.chat_contract,
    "audio_word_contract": project_contracts.audio_word_contract,
    "calendar_contract": project_contracts.calendar_contract,
    "worker_contract": project_contracts.worker_contract,
}
assert set(_PROBES) == set(CHECKS), "Automatic catalog and probe implementations differ"


def _release() -> str:
    # Do not invent a release version if the installed process doesn't expose it.
    return os.getenv("CORA_GIT_COMMIT", "").strip()[:40]


def _persist(checks: list[dict]) -> bool:
    """Only the scheduled owner writes; never store user content or stack traces."""
    from core.database import db_connection
    try:
        with db_connection() as conn:
            for entry in checks:
                conn.execute("""INSERT INTO project_health_results
                  (check_id,status,detail,source,environment,commit_sha,duration_ms)
                  VALUES (%s,%s,%s,'periodic','debian-api',%s,%s)""",
                  (entry["id"],entry["status"],entry["detail"][:240],
                   _release(),entry.get("durationMs",0)))
        return True
    except Exception:
        return False


def run_once(*, persist: bool = False) -> dict:
    """One bounded cycle of independent probes; each failure identifies a hop."""
    global _LAST
    from time import monotonic
    checks = []
    for key, probe in _PROBES.items():
        start = monotonic()
        try:
            status, detail = probe()
            if status not in {"pass","fail","unknown","skipped"}: raise ValueError("Invalid status")
        except Exception:
            status, detail = "fail", "Controllo non riuscito: verificare il componente " + key
        checks.append({"id":key, "label":CHECKS[key], "status":status,
                       "detail":str(detail)[:240], "checkedAt":_now(),
                       "durationMs":int((monotonic()-start)*1000)})
    stored = _persist(checks) if persist else False
    snap = {"checkedAt":_now(), "intervalSeconds":_INTERVAL,
            "scope":"preflight_only", "checks":checks, "persisted":stored}
    with _LOCK: _LAST = snap
    return snap


def snapshot() -> dict:
    with _LOCK:
        if _LAST is None:
            return {"checkedAt":None,"intervalSeconds":_INTERVAL,
                    "scope":"preflight_only","checks":[],"persisted":False}
        return {**_LAST, "checks":[dict(c) for c in _LAST["checks"]]}


def _scheduled_cycle():
    """PostgreSQL session advisory lock avoids duplicate checks across API workers."""
    from core.database import DATABASE_URL
    if not DATABASE_URL:
        return run_once()
    try:
        import psycopg
        with psycopg.connect(DATABASE_URL, connect_timeout=3, autocommit=True) as db:
            if not db.execute("SELECT pg_try_advisory_lock(709241009)").fetchone()[0]:
                return None
            try:
                return run_once(persist=True)
            finally:
                db.execute("SELECT pg_advisory_unlock(709241009)")
    except Exception:
        # Probes stay available, but never claim a durable history.
        return run_once()


def _loop():
    _scheduled_cycle()
    while not _STOP.wait(_INTERVAL):
        _scheduled_cycle()


def start():
    global _THREAD
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive(): return
        _STOP.clear()
        _THREAD = threading.Thread(target=_loop, name="cora-project-preflight", daemon=True)
        _THREAD.start()


def stop():
    with _LOCK:
        _STOP.set()
        worker = _THREAD
    if worker and worker.is_alive(): worker.join(timeout=3)


def health_dashboard():
    """Single source for every UI: catalog + last evidence + bounded history."""
    from core.database import db_connection
    records = []
    latest_rows = []
    store = "unavailable"
    try:
        # Reading monitoring data must never trigger schema migrations.
        with db_connection(ensure_schema=False) as conn:
            latest_rows = conn.execute("""SELECT DISTINCT ON (check_id)
              check_id,status,detail,source,environment,commit_sha,duration_ms,observed_at
              FROM project_health_results
              ORDER BY check_id,observed_at DESC,id DESC""").fetchall()
            records = conn.execute("""SELECT check_id,status,detail,source,environment,
              commit_sha,duration_ms,observed_at FROM project_health_results
              ORDER BY observed_at DESC,id DESC LIMIT 100""").fetchall()
        store = "postgresql"
    except Exception:
        pass

    def public(row):
        return {"id":row["check_id"],"status":row["status"],"detail":row["detail"],
                "source":row["source"],"environment":row["environment"],
                "commit":row["commit_sha"] or None,
                "durationMs":row["duration_ms"],"at":row["observed_at"].isoformat()}

    latest = {row["check_id"]:public(row) for row in latest_rows if row["check_id"] in CATALOG}
    history = [public(row) for row in records if row["check_id"] in CATALOG]
    volatile = snapshot()
    # Temporary snapshot is expressly labeled as such, not durable evidence.
    if not latest and volatile["checks"]:
        for check in volatile["checks"]:
            latest[check["id"]] = {
                "id":check["id"],"status":check["status"],
                "detail":check["detail"],"source":"periodic",
                "environment":"api-process-volatile",
                "commit":_release() or None,
                "durationMs":check.get("durationMs",0),
                "at":check["checkedAt"],
            }
    return {"catalog":list(CATALOG.values()),"components":CATALOG_COMPONENTS(),
            "latest":latest,"history":history[:100],"historyStore":store,
            "updatedAt":_now()}


def CATALOG_COMPONENTS():
    from core.health_catalog import COMPONENTS
    return COMPONENTS


@router.get("/project/checks")
def current_checks():
    return snapshot()


@router.get("/system/health-dashboard")
def dashboard_endpoint():
    return health_dashboard()
