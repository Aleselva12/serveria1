from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


_run_id: ContextVar[str] = ContextVar("cora_run_id", default="")
_thread_id: ContextVar[str] = ContextVar("cora_thread_id", default="")


def current_runtime() -> tuple[str, str]:
    return _run_id.get(), _thread_id.get()


@contextmanager
def bind_runtime(run_id: str, thread_id: str) -> Iterator[None]:
    run_token = _run_id.set(run_id)
    thread_token = _thread_id.set(thread_id)
    try:
        yield
    finally:
        _thread_id.reset(thread_token)
        _run_id.reset(run_token)
