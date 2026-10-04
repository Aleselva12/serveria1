"""Persistent technical traces, with no prompts, tool arguments or model output."""
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler
from core.logging import LOG_ROOT

TRACE_FILE = LOG_ROOT / "executions.jsonl"
_lock = threading.Lock()


_write_error = None

def append_event(event):
    # Diagnostic I/O cannot change a canonical run or operation outcome.
    global _write_error
    try:
        TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _lock, TRACE_FILE.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        _write_error = None
        return True
    except OSError as error:
        _write_error = type(error).__name__
        return False


def trace_status():
    return {"write_error":_write_error}


class ExecutionTrace(BaseCallbackHandler):
    raise_error = True
    run_inline = True
    def __init__(self, thread_id, graph_version):
        from core.runtime import current_run
        self.runtime_run = current_run.get()
        self.id = self.runtime_run.id if self.runtime_run else str(uuid.uuid4())
        self.model_roles = {}
        self.thread_id = thread_id
        self.graph_version = graph_version
        self.started = {}
        self.lock = threading.Lock()

    def event(self, kind, status, span_id=None, parent_id=None, name="", duration_ms=None, error_type=None):
        append_event(dict(run_id=self.id, thread_id=self.thread_id,
                          graph_version=self.graph_version,
                          timestamp=datetime.now(timezone.utc).isoformat(),
                          kind=kind, status=status, span_id=str(span_id) if span_id else None,
                          parent_id=str(parent_id) if parent_id else None,
                          name=name, duration_ms=duration_ms, error_type=error_type))

    def start(self, kind, name, run_id, parent_run_id):
        if self.runtime_run: self.runtime_run.check()
        with self.lock:
            self.started[str(run_id)] = (time.perf_counter(), kind, name)
        self.event(kind, "running", run_id, parent_run_id, name)

    def end(self, run_id, parent_run_id, error=None):
        with self.lock:
            entry = self.started.pop(str(run_id), None)
        if entry:
            start, kind, name = entry
            if self.runtime_run:
                self.runtime_run.timings.setdefault(kind + "_ms", 0)
                self.runtime_run.timings[kind + "_ms"] += round((time.perf_counter()-start)*1000,2)
            self.event(kind, "error" if error else "completed", run_id, parent_run_id,
                       name, round((time.perf_counter() - start) * 1000, 2),
                       type(error).__name__ if error else None)

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        self.start("node", kwargs.get("name") or (serialized or {}).get("name", "Graph"), run_id, parent_run_id)

    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
        role = kwargs.get("metadata", {}).get("cora_role", "unknown")
        self.model_roles[str(run_id)] = role
        if self.runtime_run:
            from core.event_bus import bus
            self.runtime_run.agents[role] = "running"
            bus.publish("agent.state", role, run_id=self.id, thread_id=self.thread_id, payload={"status": "running"})
        self.start("model", role, run_id, parent_run_id)

    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kwargs):
        self.start("tool", (serialized or {}).get("name", "Tool"), run_id, parent_run_id)

    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs):
        self.end(run_id, parent_run_id)

    def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
        if self.runtime_run:
            role = self.model_roles.pop(str(run_id), "unknown")
            self.runtime_run.agents[role] = "idle"
            usage = {}
            for group in response.generations:
                for generation in group:
                    meta = getattr(getattr(generation, "message", None), "response_metadata", {})
                    usage.update({k:v for k,v in meta.items() if k in {"prompt_eval_count", "eval_count", "load_duration", "prompt_eval_duration", "eval_duration", "total_duration"}})
            self.runtime_run.timings.setdefault("models", []).append({"role": role, **usage})
        self.end(run_id, parent_run_id)

    def on_tool_end(self, output, *, run_id, parent_run_id=None, **kwargs):
        # ToolNode may convert a tool exception into a ToolMessage.
        error = RuntimeError() if getattr(output, "status", None) == "error" else None
        self.end(run_id, parent_run_id, error)

    def on_llm_new_token(self, token, **kwargs):
        if self.runtime_run: self.runtime_run.check()

    def on_chain_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        self.end(run_id, parent_run_id, error)

    on_llm_error = on_chain_error
    on_tool_error = on_chain_error


def read_runs(limit=50, run_id=None):
    """Newest runs, with their entire stored trace (not a truncated event tail)."""
    grouped = {}
    if TRACE_FILE.exists():
        with _lock, TRACE_FILE.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                    identifier = event["run_id"]
                except (ValueError, KeyError):
                    continue
                if run_id and identifier != run_id:
                    continue
                if identifier not in grouped:
                    grouped[identifier] = []
                    if not run_id and len(grouped) > limit:
                        del grouped[next(iter(grouped))]
                grouped[identifier].append(event)
    result = []
    for identifier, events in reversed(list(grouped.items())):
        root = [e for e in events if e["kind"] == "run"]
        last = root[-1] if root else events[-1]
        status = last["status"] if root else "unknown"
        result.append(dict(id=identifier, thread_id=last["thread_id"],
                           graph_version=last["graph_version"], status=status,
                           started_at=events[0]["timestamp"], duration_ms=last["duration_ms"],
                           metrics=last.get("metrics", {}), events=events, error_count=sum(e["status"] == "error" for e in events),
                           note="Esecuzione senza evento finale: in corso o interrotta" if status in {"queued", "running", "cancelling"} else None))
    return result
