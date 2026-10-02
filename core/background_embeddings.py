"""Recoverable indexing backlog in PostgreSQL. Text persistence never waits for Ollama."""
import threading
import time
from pgvector import Vector
from core.database import db_connection
from core.embeddings import embed_text, EMBEDDING_MODEL
from core.runtime import runtime

_stop = threading.Event()
_worker = None


def index_pending_once():
    if not EMBEDDING_MODEL: return False
    # Only borrow the model slot when no foreground run is queued/running.
    with runtime.lock:
        if runtime.snapshot() or not runtime.slot.acquire(blocking=False): return False
    try:
        with db_connection() as conn:
            row = conn.execute("SELECT id,content FROM messages WHERE embedding IS NULL AND embedding_model IS NULL ORDER BY created_at LIMIT 1").fetchone()
        if not row: return False
        started = time.perf_counter()
        vector, model = embed_text(row["content"])
        if _stop.is_set(): return False
        with db_connection() as conn:
            conn.execute("UPDATE messages SET embedding=%s,embedding_model=%s,embedding_dimensions=%s WHERE id=%s AND embedding IS NULL",
                (Vector(vector) if vector else None, model or EMBEDDING_MODEL, len(vector) if vector else None, row["id"]))
        from core.logging import log_event
        log_event("message_indexing", component="embedding_worker", duration_ms=round((time.perf_counter()-started)*1000,2), status="ok" if vector else "error")
        return True
    finally:
        runtime.slot.release()


def _loop():
    while not _stop.is_set():
        try: worked = index_pending_once()
        except Exception: worked = False
        _stop.wait(.2 if worked else 3)


def start():
    global _worker
    _stop.clear()
    _worker = threading.Thread(target=_loop, daemon=True)
    _worker.start()


def stop():
    _stop.set()
    if _worker: _worker.join(timeout=1)
