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
        from core.event_bus import bus
        from core.runtime import checkpoint, current_run
        parent = current_run.get()
        checkpoint()
        bus.publish("component.request", envelope.source, run_id=parent.id if parent else envelope.run_id, thread_id=envelope.thread_id,
            component_run_id=envelope.run_id,parent_run_id=parent.id if parent else None,
            payload={"task_id":envelope.task_id,"target":envelope.target,"capability":envelope.capability,"priority":envelope.priority})
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
        except BaseException as error:
            from core.error_decisions import decide
            decision = decide(status="failed", error_code=type(error).__name__)
            self._set_state(envelope.target, status="error", error_type=type(error).__name__, last_decision=decision)
            bus.publish('component.finished',envelope.target,run_id=parent.id if parent else envelope.run_id,
                component_run_id=envelope.run_id,parent_run_id=parent.id if parent else None,thread_id=envelope.thread_id,
                payload={'task_id':envelope.task_id,'status':'failed','decision':decision,'capability':envelope.capability,
                         'error_type':type(error).__name__,'duration_ms':round((time.perf_counter()-started)*1000,2)})
            raise

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        result.duration_ms = duration_ms
        self._set_state(
            envelope.target,
            status="ready",
            last_task_id=envelope.task_id,
            last_duration_ms=duration_ms,
            error_type=None,
            last_decision=result.decision,
        )
        bus.publish("component.finished", envelope.target, run_id=parent.id if parent else envelope.run_id, thread_id=envelope.thread_id,
            component_run_id=envelope.run_id,parent_run_id=parent.id if parent else None,
            payload={"task_id":envelope.task_id,"capability":envelope.capability,"duration_ms":duration_ms,
                     "status":result.status,"decision":result.decision})
        return result



    def dispatch_capability(self, capability_id: str, payload: dict[str, Any], *, source: str | None = None) -> ComponentResult:
        """Execute one registered capability through the typed Component Bus."""
        from uuid import uuid4
        from core.runtime import current_run
        from core.runtime_context import current_runtime
        from core.governance import find_capability, execute_capability
        from core.error_decisions import decide, explanation
        from core.operational_capabilities import ACTOR_COMPONENT

        _, entry = find_capability(capability_id)
        contract = entry["contract"]
        live = current_run.get()
        runtime_run_id, runtime_thread_id = current_runtime()
        run_id = (live.id if live else runtime_run_id) or str(uuid4())
        thread_id = (live.thread_id if live else runtime_thread_id) or "direct"
        target = ACTOR_COMPONENT.get(contract.actor, contract.actor)
        envelope = TaskEnvelope(
            run_id=run_id,
            thread_id=thread_id,
            source=source or contract.actor,
            target=target,
            capability=contract.id,
            payload=payload,
        )

        def handler(task: TaskEnvelope) -> ComponentResult:
            outcome = execute_capability(task.capability, task.payload)
            error_code = outcome.error.code if outcome.error else None
            decision = decide(
                status=outcome.status,
                error_code=error_code,
                effect=contract.effect,
                retry=contract.retry,
            )
            status = "completed" if outcome.status == "ok" else "waiting_approval" if outcome.status == "pending" else "failed"
            errors = [{"code": outcome.error.code, "message": outcome.error.message}] if outcome.error else []
            return ComponentResult(
                task_id=task.task_id,
                component=target,
                status=status,
                decision=decision,
                content="" if outcome.native is None else str(outcome.native),
                errors=errors,
                next_action=None if decision == "complete" else decision,
                metadata={
                    "capability_id": contract.id,
                    "contract_version": contract.version,
                    "operation_id": outcome.operation_id,
                    "approval_id": outcome.approval_id,
                    "capability_status": outcome.status,
                    "decision_explanation": explanation(decision),
                    "native": outcome.native,
                },
            )

        return self.dispatch(envelope, handler)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {key: dict(value) for key, value in self._state.items()}


component_bus = ComponentBus()
