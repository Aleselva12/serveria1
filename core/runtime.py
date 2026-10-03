"""One local model execution at a time, bounded queue and cooperative cancellation."""
import contextvars
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from uuid import uuid4
import os
from core.event_bus import bus
from core.execution_traces import append_event
from datetime import datetime, timezone

TERMINAL = {"completed", "failed", "cancelled", "timed_out", "awaiting_approval", "interrupted"}
TRANSITIONS = {
 "queued": {"running", "cancelled", "timed_out", "interrupted"},
 "running": {"cancelling", "completed", "failed", "awaiting_approval", "interrupted"},
 "cancelling": {"cancelled", "timed_out", "failed", "interrupted"},
}
current_run = contextvars.ContextVar("cora_run", default=None)

class RunStopped(BaseException):
    pass

@dataclass
class Run:
    thread_id: str
    id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "queued"
    created: float = field(default_factory=time.monotonic)
    started: float | None = None
    finished: float | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    done: threading.Event = field(default_factory=threading.Event)
    reason: str = "cancelled"
    result: dict | None = None
    error_type: str | None = None
    approvals: list = field(default_factory=list)
    agents: dict = field(default_factory=dict)
    component_threads: set = field(default_factory=set)
    timings: dict = field(default_factory=dict)
    output: str = ""
    output_span: object = None
    timeout: float = field(default_factory=lambda: max(1, float(os.getenv("CORA_RUN_TIMEOUT_SECONDS", "300"))))
    graph_version: str = "runtime-v1"
    lock: threading.RLock = field(default_factory=threading.RLock)

    def transition(self, status):
        with self.lock:
            if status not in TRANSITIONS.get(self.status, set()):
                raise ValueError(f"Invalid run transition {self.status} -> {status}")
            self.status = status
            if status == "running": self.started = time.monotonic()
            if status in TERMINAL: self.finished = time.monotonic()
            try:
                from core.run_lifecycle import persist_live_run
                persist_live_run(self)
            except Exception:
                pass
            bus.publish("run.state", "runtime", run_id=self.id, thread_id=self.thread_id,
                        payload={"status": status})
            append_event(dict(run_id=self.id, thread_id=self.thread_id, graph_version=self.graph_version,
                timestamp=datetime.now(timezone.utc).isoformat(), kind="run", status=status,
                span_id=None, parent_id=None, name="Cora runtime", metrics=dict(self.timings) if status in TERMINAL else {}, duration_ms=round((time.monotonic()-self.created)*1000,2), error_type=self.error_type))

    def stop(self, reason="cancelled"):
        with self.lock:
            if self.status in TERMINAL: return
            self.reason = reason
            self.cancel.set()
            if self.status == "running": self.transition("cancelling")

    def check(self):
        if time.monotonic() - self.created >= self.timeout: self.stop("timed_out")
        if self.cancel.is_set(): raise RunStopped(self.reason)

    def snapshot(self):
        with self.lock:
            return {"id": self.id, "thread_id": self.thread_id, "status": self.status,
                "error_type": self.error_type, "result": self.result,
                "agents": dict(self.agents), "timings": dict(self.timings), "output": self.output,
                "approval_ids": list(self.approvals),
                "elapsed_ms": round(((self.finished or time.monotonic())-self.created)*1000,2)}

class Runtime:
    def __init__(self):
        self.runs = OrderedDict()
        self.lock = threading.RLock()
        self.slot = threading.Lock()
        self.closed = False
        self.last_foreground = time.monotonic()

    def submit(self, thread_id, execute, graph_version="runtime-v1"):
        with self.lock:
            if self.closed: raise RuntimeError("Runtime in arresto.")
            active = [r for r in self.runs.values() if r.status not in TERMINAL]
            if len(active) >= int(os.getenv("CORA_RUN_QUEUE_SIZE", "8")):
                raise ValueError("Coda piena. Riprova più tardi.")
            if any(r.thread_id == thread_id for r in active):
                raise ValueError("Questa conversazione ha già un'esecuzione attiva.")
            self.last_foreground = time.monotonic()
            run = Run(thread_id, graph_version=graph_version)
            self.runs[run.id] = run
            from core.run_lifecycle import persist_live_run
            persist_live_run(run)
            while len(self.runs) > 200:
                old = next((key for key, r in self.runs.items() if r.status in TERMINAL), None)
                if old is None: break
                del self.runs[old]
            bus.publish("run.state", "runtime", run_id=run.id, thread_id=thread_id, payload={"status": "queued"})
            append_event(dict(run_id=run.id,thread_id=thread_id,graph_version=run.graph_version,timestamp=datetime.now(timezone.utc).isoformat(),kind="run",status="queued",name="Coda",duration_ms=0,span_id=None,parent_id=None,error_type=None))
            threading.Thread(target=self._work, args=(run, execute), daemon=True).start()
            threading.Thread(target=self._deadline, args=(run,), daemon=True).start()
            return run

    def _deadline(self, run):
        if not run.done.wait(run.timeout): run.stop("timed_out")

    def _work(self, run, execute):
        acquired = False
        token = current_run.set(run)
        try:
            while not acquired:
                run.check()
                with self.lock:
                    first = next((r for r in self.runs.values() if r.status == "queued" and not r.cancel.is_set()), None)
                    if first is run:
                        acquired = self.slot.acquire(blocking=False)
                        if acquired: run.transition("running")
                if not acquired: run.cancel.wait(.1)
            run.check()
            run.timings["queue_ms"] = round((time.monotonic()-run.created)*1000,2)
            run.result = execute(run)
            run.check()
            run.transition("awaiting_approval" if run.approvals else "completed")
        except RunStopped:
            run.transition(run.reason)
        except Exception as error:
            run.error_type = type(error).__name__
            run.transition("failed")
        finally:
            for actor in run.agents: run.agents[actor] = "idle"
            try:
                from core.database import database_configured, db_connection
                if database_configured():
                    from psycopg.types.json import Jsonb
                    with db_connection() as conn:
                        conn.execute("UPDATE working_memory SET state=state || %s WHERE thread_id=ANY(%s)", (Jsonb({"status": run.status}), [run.thread_id, *run.component_threads]))
            except Exception:
                pass
            with self.lock: self.last_foreground = time.monotonic()
            if acquired: self.slot.release()
            current_run.reset(token)
            run.done.set()

    def get(self, identifier):
        with self.lock:
            return self.runs.get(identifier)

    def snapshot(self):
        with self.lock:
            return [r.snapshot() for r in self.runs.values() if r.status not in TERMINAL]

    def shutdown(self):
        with self.lock:
            self.closed = True
            for r in self.runs.values(): r.stop()

runtime = Runtime()


def publish_text(run, role, span, text):
    """Root and explicitly streamed child graphs share one provisional output."""
    if not isinstance(text, str) or not text: return
    with run.lock:
        if span != run.output_span:
            run.output_span = span
            run.output = ""
            bus.publish("chat.reset", role, run_id=run.id, thread_id=run.thread_id)
        run.timings.setdefault("first_token_ms", round((time.monotonic()-run.created)*1000,2))
        run.output += text
        bus.publish("chat.delta", role, run_id=run.id, thread_id=run.thread_id, payload={"text":text})


def checkpoint():
    run = current_run.get()
    if run:
        from core.runtime_context import _run_id, _deadline
        from core.run_lifecycle import cancel_requested
        child_id, child_deadline = _run_id.get(), _deadline.get()
        if child_id and cancel_requested(child_id): run.stop("cancelled")
        if child_deadline is not None and time.monotonic() >= child_deadline: run.stop("timed_out")
        run.check()


def recover_interrupted():
    from core.database import database_configured, db_connection
    if database_configured():
        try:
            with db_connection() as conn:
                conn.execute("UPDATE runtime_runs SET status='interrupted',finished_at=NOW() WHERE status IN ('queued','running','cancelling','waiting_approval')")
        except Exception: pass
    from core.execution_traces import read_runs
    for previous in read_runs(limit=10000):
        if previous["status"] in {"queued", "running", "cancelling"}:
            append_event(dict(run_id=previous["id"],thread_id=previous["thread_id"],
                graph_version=previous["graph_version"], timestamp=datetime.now(timezone.utc).isoformat(),
                kind="run",status="interrupted",name="Riavvio backend",span_id=None,parent_id=None,
                duration_ms=None,error_type=None))
