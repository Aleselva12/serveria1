from __future__ import annotations

import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from core.run_lifecycle import RunCancelled, cancel_requested


class RunTimedOut(RuntimeError):
    pass


_run_id: ContextVar[str] = ContextVar("cora_run_id", default="")
_thread_id: ContextVar[str] = ContextVar("cora_thread_id", default="")
_deadline: ContextVar[float | None] = ContextVar("cora_deadline", default=None)


def current_runtime() -> tuple[str, str]:
    from core.runtime import current_run
    run = current_run.get()
    return _run_id.get() or (run.id if run else ""), _thread_id.get() or (run.thread_id if run else "")


def ensure_runtime_active() -> None:
    from core.runtime import checkpoint
    checkpoint()
    deadline = _deadline.get()
    if deadline is not None and time.monotonic() >= deadline:
        raise RunTimedOut("Il tempo massimo del run è scaduto.")
    run_id = _run_id.get()
    if run_id and cancel_requested(run_id):
        raise RunCancelled("Il run è stato cancellato dal proprietario.")


@contextmanager
def bind_runtime(
    run_id: str,
    thread_id: str,
    *,
    timeout_seconds: float | None = None,
) -> Iterator[None]:
    inherited_deadline = _deadline.get()
    if inherited_deadline is not None:
        deadline = inherited_deadline
    else:
        if timeout_seconds is None:
            try:
                timeout_seconds = float(os.getenv("CORA_RUN_TIMEOUT_SECONDS", "300"))
            except ValueError:
                timeout_seconds = 300.0
        deadline = time.monotonic() + max(1.0, timeout_seconds)

    run_token = _run_id.set(run_id)
    thread_token = _thread_id.set(thread_id)
    deadline_token = _deadline.set(deadline)
    try:
        ensure_runtime_active()
        yield
    finally:
        _deadline.reset(deadline_token)
        _thread_id.reset(thread_token)
        _run_id.reset(run_token)
