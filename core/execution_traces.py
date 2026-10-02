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


def append_event(event):
    TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _lock, TRACE_FILE.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")


class ExecutionTrace(BaseCallbackHandler):
    def __init__(self, thread_id, graph_version, run_id=None):
        self.id = str(run_id or uuid.uuid4())
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
        with self.lock:
            self.started[str(run_id)] = (time.perf_counter(), kind, name)
        self.event(kind, "running", run_id, parent_run_id, name)

    def end(self, run_id, parent_run_id, error=None):
        with self.lock:
            entry = self.started.pop(str(run_id), None)
        if entry:
            start, kind, name = entry
            self.event(kind, "error" if error else "completed", run_id, parent_run_id,
                       name, round((time.perf_counter() - start) * 1000, 2),
                       type(error).__name__ if error else None)

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        self.start("node", kwargs.get("name") or (serialized or {}).get("name", "Graph"), run_id, parent_run_id)

    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
        self.start("model", (serialized or {}).get("name", "Ollama"), run_id, parent_run_id)

    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kwargs):
        self.start("tool", (serialized or {}).get("name", "Tool"), run_id, parent_run_id)

    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs):
        self.end(run_id, parent_run_id)

    def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
        self.end(run_id, parent_run_id)

    def on_tool_end(self, output, *, run_id, parent_run_id=None, **kwargs):
        # ToolNode may convert a tool exception into a ToolMessage.
        error = RuntimeError() if getattr(output, "status", None) == "error" else None
        self.end(run_id, parent_run_id, error)

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
                           events=events, error_count=sum(e["status"] == "error" for e in events),
                           note="Esecuzione senza evento finale: in corso o interrotta" if status == "running" else None))
    return result
