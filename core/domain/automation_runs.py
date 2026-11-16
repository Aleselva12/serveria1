"""Manual runs of automation drafts: queue, background runner and run records.

One run executes at a time in a background thread of the API process, so a slow tool
never blocks an HTTP request. A run that needs the owner's confirmation pauses without
holding the queue; when the request is resolved in Attività (which executes the tool
with its exact parameters) the run resumes from the next node.

After a restart, runs that were executing are marked interrupted and never replayed;
runs waiting for a confirmation keep waiting, since their state is on disk.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path

from core.domain import automation_drafts as drafts
from core.domain import automation_engine as engine

ACTIVE = {"queued", "running", "waiting_approval"}
FINAL = {"succeeded", "failed", "rejected", "cancelled", "interrupted"}
POLL_SECONDS = 15
_LOCK = threading.RLock()
_WAKE = threading.Event()
_STOP = threading.Event()
_CANCEL = set()
_THREAD = None
_RUNNER_LOCK = None


def run_root():
    # Default next to the drafts folder (/state/automation_drafts in Docker), so the
    # runs persist on the state volume without a compose.yml change, which the host
    # updater refuses to apply as an ordinary release.
    configured = os.getenv("CORA_AUTOMATION_RUNS_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return drafts.draft_root().parent / "automation_runs"


def time_limit():
    """Seconds of active execution per run; time spent waiting for a confirmation is excluded."""
    try:
        return max(30, int(os.getenv("CORA_AUTOMATION_RUN_TIMEOUT_SECONDS", "1800")))
    except ValueError:
        return 1800


def _path(run_id, root=None):
    try:
        parsed = str(uuid.UUID(run_id))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Identificativo dell’esecuzione non valido.") from None
    return (root or run_root()) / (parsed + ".json")


def _write(record, root=None):
    root = root or run_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix=".run-", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, allow_nan=False, default=str)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, _path(record["id"], root))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def get_run(run_id, root=None):
    with _LOCK:
        return json.loads(_path(run_id, root).read_text(encoding="utf-8"))


def _all(root=None):
    root = root or run_root()
    if not root.is_dir():
        return []
    rows = []
    for path in root.glob("*.json"):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return sorted(rows, key=lambda row: row["created_at"], reverse=True)


def summary(run):
    return {key: run.get(key) for key in ("id", "draft_id", "draft_version", "title", "mode", "status",
                                          "created_at", "started_at", "finished_at", "error")}


def list_runs(draft_id, root=None, limit=50):
    with _LOCK:
        return [summary(run) for run in _all(root) if run["draft_id"] == draft_id][:limit]


def bindings_from_inventory(entries):
    """Inventory tool id -> the exact capability the runner calls, with its effect and schema."""
    result = {}
    for entry in entries:
        capabilities = entry.get("capabilities") or []
        if entry.get("kind") == "planned" or not capabilities:
            continue
        first = capabilities[0]
        result[entry["id"]] = {"capability": first["tool_id"], "contract_id": first["id"], "effect": first["effect"],
                               "input_schema": first.get("input_schema") or {}, "actor": first["actor"]}
    return result


class RunRejected(ValueError):
    """The run cannot start; ``problems`` lists the reasons for the owner."""

    def __init__(self, message, problems=()):
        super().__init__(message)
        self.problems = list(problems)


def create_run(draft_id, version, mode, run_input, bindings, root=None, draft_root=None):
    if mode not in {"dry_run", "live"}:
        raise ValueError("Modalità non valida.")
    if not isinstance(run_input, dict) or len(json.dumps(run_input, ensure_ascii=False, default=str)) > 65536:
        raise ValueError("Valori di avvio non validi o troppo grandi.")
    draft = drafts.get_draft(draft_id, draft_root)
    if draft["version"] != version:
        raise drafts.VersionConflict("La bozza è cambiata. Ricaricala e salva prima di eseguire.")
    graph = {"nodes": draft["nodes"], "edges": draft["edges"]}
    used = {n.get("tool_id") for n in graph["nodes"] if n["kind"] == "tool"}
    snapshot = {key: value for key, value in bindings.items() if key in used}
    problems = engine.preflight(graph, snapshot)
    missing = [name for name in engine.input_names(graph) if name not in run_input]
    problems += [f"Manca il valore di avvio «{name}»." for name in missing]
    if problems:
        raise RunRejected("Il flusso non può essere eseguito.", problems)
    record = {"id": str(uuid.uuid4()), "draft_id": draft_id, "draft_version": version, "title": draft["title"],
              "mode": mode, "status": "queued", "input": run_input, "created_at": engine.now(), "started_at": None,
              "finished_at": None, "error": None, "active_seconds": 0.0,
              # Graph and tool bindings are frozen at start: a resumed run executes what the owner launched.
              "graph": graph, "bindings": snapshot, "nodes": engine.new_run_nodes(graph)}
    with _LOCK:
        _write(record, root)
    _WAKE.set()
    return record


def cancel_run(run_id, root=None):
    with _LOCK:
        run = get_run(run_id, root)
        if run["status"] not in ACTIVE:
            raise drafts.VersionConflict("L’esecuzione è già terminata.")
        if run["status"] == "running":
            _CANCEL.add(run_id)  # stops before the next node; a tool already running finishes
            return run
        run.update(status="cancelled", finished_at=engine.now(), error="Esecuzione annullata dall’utente.")
        for state in run["nodes"].values():
            if state["status"] == "waiting_approval":
                state.update(status="cancelled", note="La richiesta in Attività resta da gestire: annullare l’esecuzione non la ritira.")
        _write(run, root)
        return run


def approval_decision(approval_id):
    """Current state of a confirmation request, from the action or calendar approval store."""
    from core.infra.database import db_connection
    if approval_id.startswith("calendar:"):
        with db_connection() as conn:
            row = conn.execute("SELECT status FROM calendar_proposals WHERE id=%s", (uuid.UUID(approval_id[9:]),)).fetchone()
        if not row:
            return {"status": "failed", "error_type": "ProposalMissing"}
        return {"status": row["status"], "result": {"proposal_id": approval_id[9:], "status": row["status"]}}
    with db_connection() as conn:
        row = conn.execute("SELECT status, result, error_type, expires_at < NOW() AS expired FROM action_approvals WHERE id=%s",
                           (uuid.UUID(approval_id),)).fetchone()
    if not row:
        return {"status": "failed", "error_type": "ApprovalMissing"}
    if row["status"] == "pending":
        return {"status": "expired" if row["expired"] else "pending"}
    return {"status": row["status"], "result": row["result"], "error_type": row["error_type"]}


def _execute(capability, payload):
    from core.governance import execute_capability
    return execute_capability(capability, payload)


def process(run, root=None, execute=_execute, decide=approval_decision):
    """Advance one run as far as possible. Returns the updated record."""
    with _LOCK:
        fresh = get_run(run["id"], root)
    if fresh["status"] != run["status"]:
        return fresh  # cancelled while it was waiting in the queue
    run = fresh
    if run["status"] == "waiting_approval":
        waiting = [(node_id, state) for node_id, state in run["nodes"].items() if state["status"] == "waiting_approval"]
        for node_id, state in waiting:
            decision = decide(state["approval_id"])
            if decision["status"] == "pending":
                return run
            engine.apply_approval(run, node_id, decision)
    if run["status"] == "queued":
        run["started_at"] = engine.now()
    started = time.monotonic()
    budget = time_limit() - run.get("active_seconds", 0.0)

    def should_stop():
        if run["id"] in _CANCEL:
            return True
        if time.monotonic() - started > budget:
            run["timed_out"] = True
            return True
        return False

    def persist(current):
        with _LOCK:
            _write(current, root)

    run["status"] = "running"
    persist(run)
    try:
        engine.advance(run, run["graph"], run["bindings"], execute, should_stop=should_stop, persist=persist)
    except Exception as error:  # a defect in the engine must not leave the run "running"
        run.update(status="failed", error="Errore interno dell’esecutore (" + type(error).__name__ + ").")
    if run.pop("timed_out", False) and run["status"] == "cancelled":
        run["status"], run["error"] = "failed", "Tempo massimo di esecuzione superato."
    run["active_seconds"] = round(run.get("active_seconds", 0.0) + time.monotonic() - started, 1)
    if run["status"] in FINAL:
        run["finished_at"] = engine.now()
    _CANCEL.discard(run["id"])
    persist(run)
    return run


def _next_queued(root=None):
    queued = [run for run in _all(root) if run["status"] == "queued"]
    return min(queued, key=lambda run: run["created_at"]) if queued else None


def _loop():
    last_poll = 0.0
    while not _STOP.is_set():
        try:
            run = _next_queued()
            if run:
                process(run)
                continue
            if time.monotonic() - last_poll >= POLL_SECONDS:
                last_poll = time.monotonic()
                for waiting in [r for r in _all() if r["status"] == "waiting_approval"]:
                    try:
                        process(waiting)
                    except Exception:
                        continue  # database unavailable: retry at the next poll
        except Exception:
            pass
        _WAKE.wait(POLL_SECONDS)
        _WAKE.clear()


def recover_interrupted(root=None):
    with _LOCK:
        for run in _all(root):
            if run["status"] != "running":
                continue
            for state in run["nodes"].values():
                if state["status"] == "running" or (state["status"] == "pending" and state.get("started_at")):
                    state.update(status="failed", error="interrotto dal riavvio: controlla in Attività l’esito prima di ripetere.")
            run.update(status="interrupted", finished_at=engine.now(),
                       error="Esecuzione interrotta dal riavvio del server. Non viene ripresa automaticamente.")
            _write(run, root)


def runner_active():
    return _RUNNER_LOCK is not None


def _acquire_runner_lock():
    """Only one process per state directory runs automations (see mail_summary_jobs)."""
    global _RUNNER_LOCK
    try:
        run_root().mkdir(parents=True, exist_ok=True, mode=0o700)
        handle = open(run_root() / "runner.lock", "a+")
    except OSError:
        return False
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return False
    _RUNNER_LOCK = handle
    return True


def start():
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return
    if _RUNNER_LOCK is None and not _acquire_runner_lock():
        return
    try:
        recover_interrupted()
    except OSError:
        pass
    _STOP.clear()
    _THREAD = threading.Thread(target=_loop, daemon=True, name="cora-automation-runs")
    _THREAD.start()


def stop():
    global _RUNNER_LOCK
    _STOP.set()
    _WAKE.set()
    if _THREAD:
        _THREAD.join(timeout=2)
    if _RUNNER_LOCK is not None:
        try:
            fcntl.flock(_RUNNER_LOCK, fcntl.LOCK_UN)
        finally:
            _RUNNER_LOCK.close()
            _RUNNER_LOCK = None
