"""Recoverable indexing backlog in PostgreSQL. Text persistence never waits for Ollama."""
import os
import threading
import time
from pgvector import Vector
from core.database import db_connection
from core.embeddings import embed_batch, EMBEDDING_MODEL
from core.runtime import runtime

_stop = threading.Event()
_worker = None


def index_pending_once():
    # Only borrow the model slot when no foreground run is queued/running.
    with runtime.lock:
        if runtime.closed or runtime.snapshot() or time.monotonic()-runtime.last_foreground < float(os.getenv("CORA_BACKGROUND_IDLE_SECONDS", "15")) or not runtime.slot.acquire(blocking=False): return False
    try:
        from core.context_budget import prepare_context, ContextDeferred
        with db_connection() as conn:
            job = conn.execute("SELECT * FROM context_jobs ORDER BY updated_at LIMIT 1").fetchone()
        if job:
            try:
                prepare_context(str(job["conversation_id"]), should_yield=lambda: _stop.is_set() or bool(runtime.snapshot()))
            except ContextDeferred:
                return False
            with db_connection() as conn:
                conn.execute("DELETE FROM context_jobs WHERE conversation_id=%s AND updated_at=%s", (job["conversation_id"],job["updated_at"]))
            return True
        if not EMBEDDING_MODEL: return False
        with db_connection() as conn:
            memories = conn.execute("""SELECT id,content,version FROM memories
                WHERE embedding IS NULL AND embedding_model IS NULL
                AND (expires_at IS NULL OR expires_at>NOW()) ORDER BY updated_at LIMIT 2""").fetchall()
        if memories:
            vectors = embed_batch([row['content'] for row in memories])
            if _stop.is_set(): return False
            with db_connection() as conn:
                for row, vector in zip(memories,vectors):
                    conn.execute("""UPDATE memories SET embedding=%s,embedding_model=%s,embedding_dimensions=%s
                        WHERE id=%s AND version=%s AND embedding IS NULL""",
                        (Vector(vector) if vector else None,EMBEDDING_MODEL,len(vector) if vector else None,row['id'],row['version']))
            return True
        with db_connection() as conn:
            rows = conn.execute("SELECT id,content FROM messages WHERE embedding IS NULL AND embedding_model IS NULL ORDER BY created_at LIMIT %s", (max(1,min(8,int(os.getenv("CORA_EMBEDDING_BATCH_SIZE", "2")))),)).fetchall()
        if not rows: return False
        started = time.perf_counter()
        vectors = embed_batch([row["content"] for row in rows])
        if _stop.is_set(): return False
        with db_connection() as conn:
            for row, vector in zip(rows,vectors):
                conn.execute("UPDATE messages SET embedding=%s,embedding_model=%s,embedding_dimensions=%s WHERE id=%s AND embedding IS NULL",
                    (Vector(vector) if vector else None, EMBEDDING_MODEL, len(vector) if vector else None, row["id"]))
        from core.logging import log_event
        log_event("message_indexing", component="embedding_worker", duration_ms=round((time.perf_counter()-started)*1000,2), status="ok" if all(vectors) else "error", data={"message_count":len(rows)})
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
