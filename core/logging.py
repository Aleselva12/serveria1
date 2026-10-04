from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

LOG_ROOT = Path(os.getenv("CORA_LOG_ROOT", str(PROJECT_ROOT / "logs"))).expanduser().resolve()
LOG_FILE = LOG_ROOT / "cora.jsonl"
_LOCK = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(
    event_type: str,
    *,
    component: str,
    status: str = "ok",
    thread_id: str | None = None,
    duration_ms: float | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compatibility adapter to the single metadata-only diagnostic event path."""
    from core.event_bus import bus
    from core.runtime import current_run
    from core.runtime_context import current_runtime
    from core.observability import metadata_event
    run = current_run.get()
    component_run, active_thread = current_runtime()
    event_id, timestamp = str(uuid.uuid4()), _utc_now()
    try:
        selected = metadata_event({'type':'log.'+event_type,'payload':{**(data or {}),'status':status,
            'duration_ms':round(duration_ms,2) if duration_ms is not None else None}})
        published = bus.publish('log.'+event_type,component,run_id=run.id if run else component_run or None,
            component_run_id=component_run or None,thread_id=thread_id or active_thread or None,payload=selected['payload'])
        event_id, timestamp = published.id, published.timestamp
    except Exception as error:
        from core.observability import archive
        with archive.lock:
            archive.dropped += 1
            archive.last_error = type(error).__name__
        selected = {'payload':{}}
    event = {
        "event_id": event_id,
        "timestamp": timestamp,
        "event_type": event_type,
        "component": component,
        "status": status,
        "thread_id": thread_id,
        "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
        "data": selected['payload'],
    }
    return event


@contextmanager
def logged_operation(
    event_type: str,
    *,
    component: str,
    thread_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """Measure an operation and write one success/error event when it ends."""
    started = time.perf_counter()
    context: dict[str, Any] = {"result": None}
    try:
        yield context
    except BaseException as error:
        log_event(
            event_type,
            component=component,
            status="error",
            thread_id=thread_id,
            duration_ms=(time.perf_counter() - started) * 1000,
            data={**(data or {}), "error_type": type(error).__name__},
        )
        raise
    else:
        extra = context.get("result")
        payload = dict(data or {})
        if isinstance(extra, dict):
            payload.update(extra)
        log_event(
            event_type,
            component=component,
            status="ok",
            thread_id=thread_id,
            duration_ms=(time.perf_counter() - started) * 1000,
            data=payload,
        )


def tail_events(limit: int = 50, event_type: str = "", component: str = "") -> list[dict[str, Any]]:
    """SQL metadata diagnostics only; legacy full-content logs are not reimported."""
    from core.database import db_connection
    with db_connection() as connection:
        rows = connection.execute('''SELECT event FROM diagnostic_events WHERE type LIKE 'log.%%'
            AND (%s='' OR type=%s) AND (%s='' OR source=%s) ORDER BY timestamp DESC,id DESC LIMIT %s''',
            (event_type,'log.'+event_type,component,component,max(1,min(limit,500)))).fetchall()
    return [dict(event_id=e['id'],timestamp=e['timestamp'],event_type=e['type'][4:],component=e['source'],
                 status=e['payload'].get('status'),thread_id=e['thread_id'],duration_ms=e['payload'].get('duration_ms'),data=e['payload'])
            for e in reversed([r['event'] for r in rows])]
