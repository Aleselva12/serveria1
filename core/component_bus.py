from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from core.protocol import ComponentResult, TaskEnvelope


Handler = Callable[[TaskEnvelope], ComponentResult | str | dict[str, Any]]


class ComponentBus:
    """
    In-process typed bus.

    Components in the same Python process communicate by direct function call:
    no Redis/network hop and no JSON serialization is required. A distributed
    transport can later implement the same TaskEnvelope/ComponentResult contract.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state: dict[str, dict[str, Any]] = {}

    def _set_state(self, component: str, **state: Any) -> None:
        with self._lock:
            self._state[component] = {**self._state.get(component, {}), **state}

    def dispatch(self, envelope: TaskEnvelope, handler: Handler) -> ComponentResult:
        started = time.perf_counter()
        self._set_state(
            envelope.target,
            status="busy",
            task_id=envelope.task_id,
            run_id=envelope.run_id,
            thread_id=envelope.thread_id,
        )
        try:
            raw = handler(envelope)
            if isinstance(raw, ComponentResult):
                result = raw
            elif isinstance(raw, str):
                result = ComponentResult(
                    task_id=envelope.task_id,
                    component=envelope.target,
                    content=raw,
                )
            elif isinstance(raw, dict):
                result = ComponentResult(
                    task_id=envelope.task_id,
                    component=envelope.target,
                    content=str(raw.get("content", "")),
                    artifacts=list(raw.get("artifacts", [])),
                    observations=list(raw.get("observations", [])),
                    metadata={k: v for k, v in raw.items() if k not in {"content", "artifacts", "observations"}},
                )
            else:
                raise TypeError(f"Risultato componente non supportato: {type(raw).__name__}")
        except Exception as error:
            self._set_state(envelope.target, status="error", error_type=type(error).__name__)
            raise

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        result.duration_ms = duration_ms
        self._set_state(
            envelope.target,
            status="ready",
            last_task_id=envelope.task_id,
            last_duration_ms=duration_ms,
            error_type=None,
        )
        return result

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {key: dict(value) for key, value in self._state.items()}


component_bus = ComponentBus()
