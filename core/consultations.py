"""Private chat evidence, separate from diagnostics. Never stores arguments or content."""
import threading
from uuid import UUID
from core.database import database_configured, db_connection

_lock = threading.Lock()
_failures = 0


def record(kind, name, status, *, run=None):
    global _failures
    if run is None:
        from core.runtime import current_run
        run = current_run.get()
    if not run or not database_configured(): return
    try: conversation = UUID(str(run.thread_id))
    except (ValueError,TypeError,AttributeError): return
    try:
        with db_connection() as conn:
            # Non-chat runs and deleted conversations must not recreate chat history.
            conn.execute('''INSERT INTO chat_consultations(conversation_id,run_id,kind,name,status)
                SELECT id,%s,%s,%s,%s FROM conversations WHERE id=%s''',
                (UUID(str(run.id)),kind,str(name)[:500],status,conversation))
    except Exception:
        # A failed evidence write must never cause a completed tool to be retried.
        with _lock: _failures += 1


def read(conversation_id, before=None, limit=100):
    with db_connection() as conn:
        rows = conn.execute('''SELECT id,run_id,created_at,kind,name,status FROM chat_consultations
            WHERE conversation_id=%s AND (%s::bigint IS NULL OR id<%s)
            ORDER BY id DESC LIMIT %s''',
            (conversation_id,before,before,limit+1)).fetchall()
    selected = rows[:limit]
    return {'items':selected,'next_before':selected[-1]['id'] if len(rows)>limit else None,
            'write_failures_since_restart':_failures}
