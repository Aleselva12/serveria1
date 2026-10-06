"""Persistent technical traces, with no prompts, tool arguments or model output."""
import json
import math
import threading
import time
import uuid
import os
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler
from core.logging import LOG_ROOT
from core.database import database_configured

TRACE_FILE = LOG_ROOT / "executions.jsonl"
_lock = threading.Lock()


_write_error = None

def _safe_error_detail(error):
    """Bounded provider error only: never prompt, messages, tool args or model output."""
    if error is None:
        return None
    detail = str(error).replace("\n", " ").strip()
    return detail[:500] if detail else None


def append_event(event):
    # Diagnostic I/O cannot change a canonical run or operation outcome.
    global _write_error
    try:
        from core.event_bus import bus
        published = bus.publish('trace.span','tracing',run_id=event.get('run_id'),thread_id=event.get('thread_id'),
            span_id=event.get('span_id'),parent_span_id=event.get('parent_id'),
            payload={k:event.get(k) for k in ('kind','status','name','duration_ms','error_type','error_detail','graph_version')})
        # Optional metadata-only export. SQL remains the authoritative trace view.
        if os.getenv('CORA_DIAGNOSTIC_JSONL_EXPORT','').lower() != 'true': return True
        TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _lock, TRACE_FILE.open("a", encoding="utf-8") as stream:
            exported = {k:event.get(k) for k in ('run_id','thread_id','timestamp','kind','status','name','duration_ms','error_type','error_detail','graph_version','span_id','parent_id')}
            exported['event_id'] = published.id
            stream.write(json.dumps(exported, ensure_ascii=False) + "\n")
        _write_error = None
        return True
    except Exception as error:
        _write_error = type(error).__name__
        return False


def trace_status():
    from core.observability import archive
    return {"write_error":_write_error,"diagnostics":archive.status()}


class ExecutionTrace(BaseCallbackHandler):
    raise_error = True
    run_inline = True
    def __init__(self, thread_id, graph_version):
        from core.runtime import current_run
        self.runtime_run = current_run.get()
        self.id = self.runtime_run.id if self.runtime_run else str(uuid.uuid4())
        self.model_roles = {}
        self.model_started = {}
        self.model_first_token = {}
        self.thread_id = thread_id
        self.graph_version = graph_version
        self.started = {}
        self.lock = threading.Lock()

    def event(self, kind, status, span_id=None, parent_id=None, name="", duration_ms=None, error_type=None, error_detail=None):
        append_event(dict(run_id=self.id, thread_id=self.thread_id,
                          graph_version=self.graph_version,
                          timestamp=datetime.now(timezone.utc).isoformat(),
                          kind=kind, status=status, span_id=str(span_id) if span_id else None,
                          parent_id=str(parent_id) if parent_id else None,
                          name=name, duration_ms=duration_ms, error_type=error_type, error_detail=error_detail))

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
                       type(error).__name__ if error else None, _safe_error_detail(error))

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        self.start("node", kwargs.get("name") or (serialized or {}).get("name", "Graph"), run_id, parent_run_id)

    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
        role = kwargs.get("metadata", {}).get("cora_role", "unknown")
        self.model_roles[str(run_id)] = role
        self.model_started[str(run_id)] = time.perf_counter()
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
        role = self.model_roles.pop(str(run_id), "unknown")
        started = self.model_started.pop(str(run_id),None)
        first = self.model_first_token.pop(str(run_id),None)
        if self.runtime_run:
            self.runtime_run.agents[role] = "idle"
            usage = {}
            for group in response.generations:
                for generation in group:
                    meta = getattr(getattr(generation, "message", None), "response_metadata", {})
                    usage.update({k:v for k,v in meta.items() if k in {"prompt_eval_count", "eval_count", "load_duration", "prompt_eval_duration", "eval_duration", "total_duration"}
                                  and isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0})
            duration = (time.perf_counter()-started)*1000 if started is not None else None
            self.runtime_run.timings.setdefault("models", []).append({"role": role,"span_id":str(run_id),
                "duration_ms":duration,"first_token_ms":(first-started)*1000 if first is not None and started is not None else None,**usage})
            from core.event_bus import bus
            bus.publish('agent.state',role,run_id=self.id,thread_id=self.thread_id,payload={'status':'idle'})
        self.end(run_id, parent_run_id)

    def on_tool_end(self, output, *, run_id, parent_run_id=None, **kwargs):
        # ToolNode may convert a tool exception into a ToolMessage.
        error = RuntimeError() if getattr(output, "status", None) == "error" else None
        self.end(run_id, parent_run_id, error)

    def on_llm_new_token(self, token, *, run_id=None, **kwargs):
        if self.runtime_run: self.runtime_run.check()
        if token and run_id is not None: self.model_first_token.setdefault(str(run_id),time.perf_counter())

    def on_chain_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        self.end(run_id, parent_run_id, error)

    def on_llm_error(self,error,*,run_id,parent_run_id=None,**kwargs):
        role = self.model_roles.pop(str(run_id),'unknown')
        started = self.model_started.pop(str(run_id),None)
        first = self.model_first_token.pop(str(run_id),None)
        if self.runtime_run:
            self.runtime_run.agents[role] = 'idle'
            self.runtime_run.timings.setdefault('models',[]).append({'role':role,'span_id':str(run_id),'error_type':type(error).__name__,
                'duration_ms':(time.perf_counter()-started)*1000 if started is not None else None,
                'first_token_ms':(first-started)*1000 if first is not None and started is not None else None})
            from core.event_bus import bus
            bus.publish('agent.state',role,run_id=self.id,thread_id=self.thread_id,payload={'status':'idle'})
        self.end(run_id,parent_run_id,error)
    on_tool_error = on_chain_error


def read_runs(limit=50, run_id=None,include_events=True):
    """Canonical lifecycle plus explicitly bounded diagnostic samples."""
    if database_configured() or os.getenv('CORA_DIAGNOSTIC_JSONL_EXPORT','').lower() != 'true':
        from core.run_lifecycle import get_run,persisted_snapshot
        from core.database import db_connection
        from core.observability import read
        if run_id: rows = [get_run(run_id)]
        else:
            with db_connection() as conn:
                rows = conn.execute('SELECT * FROM runtime_runs WHERE parent_run_id IS NULL ORDER BY created_at DESC LIMIT %s',
                                    (max(1,min(limit,100)),)).fetchall()
        result = []
        for row in rows:
            snapshot = persisted_snapshot(row)
            root = str(row['id'])
            if row['parent_run_id']:
                from core.domain_events import root_for
                with db_connection() as conn: root = root_for(conn,row['id'])
            page = read(run_id=root,limit=200) if include_events else {'events':[],'truncated':False}
            events = []
            for event in page['events']:
                if event['type'] != 'trace.span' or (row['parent_run_id'] and event.get('component_run_id') != str(row['id'])): continue
                payload = event['payload']
                events.append(dict(timestamp=event['timestamp'],span_id=event.get('span_id'),parent_id=event.get('parent_span_id'),
                                   component_run_id=event.get('component_run_id'),**payload))
            result.append(dict(id=snapshot['id'],thread_id=snapshot['thread_id'],graph_version=row['metadata'].get('graph_version','unknown'),
                status=snapshot['status'],started_at=row['created_at'],duration_ms=snapshot['elapsed_ms'],metrics=snapshot['timings'],
                events=events,error_count=sum(e.get('status')=='error' for e in events),diagnostic_truncated=page['truncated'],
                note='Campione diagnostico best-effort (30 giorni predefiniti). Lo stato proviene dal lifecycle PostgreSQL; eventi pendenti, perduti o scaduti non indicano assenza di esecuzione.'))
        return result
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
