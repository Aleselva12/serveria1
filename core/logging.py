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
    """Append one structured event to Cora's local JSONL log."""
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": str(uuid.uuid4()),
        "timestamp": _utc_now(),
        "event_type": event_type,
        "component": component,
        "status": status,
        "thread_id": thread_id,
        "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
        "data": data or {},
    }

    line = json.dumps(event, ensure_ascii=False, default=str)
    with _LOCK:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
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
    except Exception as error:
        log_event(
            event_type,
            component=component,
            status="error",
            thread_id=thread_id,
            duration_ms=(time.perf_counter() - started) * 1000,
            data={**(data or {}), "error_type": type(error).__name__, "error": str(error)},
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
    """Return recent log events without loading unbounded history into memory."""
    if not LOG_FILE.exists():
        return []

    limit = max(1, min(int(limit), 500))
    selected: list[dict[str, Any]] = []

    with LOG_FILE.open("r", encoding="utf-8") as handle:
        lines = deque(handle, maxlen=2000)

    for line in reversed(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event_type and event.get("event_type") != event_type:
            continue
        if component and event.get("component") != component:
            continue

        selected.append(event)
        if len(selected) >= limit:
            break

    selected.reverse()
    return selected
