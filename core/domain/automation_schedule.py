"""Scheduled starts of automation drafts.

A draft is scheduled by the configuration of its first start node::

    {"schedule": {"enabled": true, "time": "08:00", "days": [0, 1, 2, 3, 4], "mode": "dry_run"},
     "input": {"name": "value"}}

Days count from Monday = 0, the time is local (``CORA_TIMEZONE``, default Europe/Rome).
Each slot starts at most once: the slot is recorded before the run is queued, so a run
that cannot start is reported, not retried every tick. A slot missed by more than the
catch-up window (server off, restart) is skipped, never replayed later in the day.

The schedule queues an ordinary run in the same runner as manual runs, so the usual
rules hold: live write tools still ask for the owner's confirmation in Attività.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.domain import automation_drafts as drafts
from core.domain import automation_runs as runs

TICK_SECONDS = 30
CATCH_UP = timedelta(minutes=10)
ALL_DAYS = [0, 1, 2, 3, 4, 5, 6]
TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_LOCK = threading.RLock()
_STOP = threading.Event()
_THREAD = None


def timezone():
    try:
        return ZoneInfo(os.getenv("CORA_TIMEZONE", "Europe/Rome").strip() or "Europe/Rome")
    except (KeyError, ValueError):
        return ZoneInfo("Europe/Rome")


def schedule_problems(config):
    """Owner-facing problems of a start node's schedule; empty when absent or valid."""
    raw = (config or {}).get("schedule")
    if raw is None:
        return []
    if not isinstance(raw, dict):
        return ["la pianificazione non è valida."]
    problems = []
    if not isinstance(raw.get("time"), str) or not TIME.match(raw["time"]):
        problems.append("orario della pianificazione non valido (usa HH:MM).")
    days = raw.get("days", ALL_DAYS)
    if not isinstance(days, list) or not days or any(isinstance(d, bool) or d not in ALL_DAYS for d in days):
        problems.append("giorni della pianificazione non validi.")
    if raw.get("mode", "dry_run") not in {"dry_run", "live"}:
        problems.append("modalità della pianificazione non valida.")
    if not isinstance(raw.get("enabled", False), bool):
        problems.append("stato della pianificazione non valido.")
    inputs = (config or {}).get("input", {})
    if not isinstance(inputs, dict):
        problems.append("i valori di avvio devono essere un oggetto.")
    return problems


def schedule_of(draft):
    """The enabled, valid schedule of a draft with its start values, or None."""
    trigger = next((n for n in draft.get("nodes", []) if n.get("kind") == "trigger"), None)
    config = (trigger or {}).get("config") or {}
    raw = config.get("schedule")
    if not isinstance(raw, dict) or raw.get("enabled") is not True or schedule_problems(config):
        return None
    hour, minute = (int(part) for part in raw["time"].split(":"))
    return {"hour": hour, "minute": minute, "days": sorted(set(raw.get("days", ALL_DAYS))),
            "mode": raw.get("mode", "dry_run"), "input": dict(config.get("input") or {})}


def due_slot(schedule, now):
    """Slot key ("YYYY-MM-DD HH:MM") if ``now`` (aware, local) is inside today's start window."""
    start = now.replace(hour=schedule["hour"], minute=schedule["minute"], second=0, microsecond=0)
    if now.weekday() not in schedule["days"] or not start <= now < start + CATCH_UP:
        return None
    return start.strftime("%Y-%m-%d %H:%M")


def next_start(schedule, now):
    for offset in range(8):
        day = (now + timedelta(days=offset)).replace(hour=schedule["hour"], minute=schedule["minute"], second=0, microsecond=0)
        if day.weekday() in schedule["days"] and day > now:
            return day
    return None


def _state_path(root=None):
    # Next to the runs folder, not inside it: every *.json there is read as a run record.
    return (root or runs.run_root()).parent / "automation_schedule.json"


def read_state(root=None):
    try:
        data = json.loads(_state_path(root).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_state(state, root=None):
    path = _state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix=".schedule-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _bindings():
    from core.tool_inventory import inventory
    return runs.bindings_from_inventory(inventory()["entries"])


def tick(now=None, *, bindings=None, create=None, draft_root=None, run_root=None):
    """Queue every scheduled draft whose slot is due. Returns {draft_id: outcome}."""
    now = now or datetime.now(timezone())
    create = create or runs.create_run
    outcomes = {}
    with _LOCK:
        state = read_state(run_root)
        for row in drafts.list_drafts(draft_root):
            try:
                draft = drafts.get_draft(row["id"], draft_root)
            except (OSError, ValueError):
                continue
            schedule = schedule_of(draft)
            slot = schedule and due_slot(schedule, now)
            entry = state.get(draft["id"]) or {}
            if not slot or entry.get("slot") == slot:
                continue
            if any(r["status"] in runs.ACTIVE for r in runs.list_runs(draft["id"], run_root, limit=5)):
                entry = {"slot": slot, "outcome": "skipped", "error": "Un'esecuzione precedente non è ancora terminata."}
            else:
                # Record the slot first: a failure is reported once, never retried in a loop.
                state[draft["id"]] = {"slot": slot, "outcome": "starting"}
                _write_state(state, run_root)
                try:
                    run = create(draft["id"], draft["version"], schedule["mode"], schedule["input"],
                                 bindings if bindings is not None else _bindings(), root=run_root, draft_root=draft_root,
                                 origin="schedule")
                    entry = {"slot": slot, "outcome": "queued", "run_id": run["id"]}
                except runs.RunRejected as error:
                    entry = {"slot": slot, "outcome": "rejected", "error": "; ".join(error.problems) or str(error)}
                except (OSError, ValueError) as error:
                    entry = {"slot": slot, "outcome": "failed", "error": str(error)}
            state[draft["id"]] = entry
            outcomes[draft["id"]] = entry
        if outcomes:
            _write_state(state, run_root)
    return outcomes


def overview(now=None, draft_root=None, run_root=None):
    """Scheduled drafts with their next start and the outcome of the last slot."""
    now = now or datetime.now(timezone())
    state = read_state(run_root)
    rows = []
    for row in drafts.list_drafts(draft_root):
        try:
            schedule = schedule_of(drafts.get_draft(row["id"], draft_root))
        except (OSError, ValueError):
            continue
        if not schedule:
            continue
        upcoming = next_start(schedule, now)
        rows.append({"draft_id": row["id"], "title": row["title"], "mode": schedule["mode"],
                     "time": f"{schedule['hour']:02d}:{schedule['minute']:02d}", "days": schedule["days"],
                     "next_start": upcoming.isoformat() if upcoming else None, "last": state.get(row["id"])})
    return rows


def _loop():
    while not _STOP.is_set():
        try:
            if runs.runner_active():
                tick()
        except Exception as error:
            # Keep the scheduler alive; a bad tick must not silently stop all schedules.
            from core.infra.logging import report_swallowed_error
            report_swallowed_error("automation_schedule_tick", error, component="automation_scheduler")
        _STOP.wait(TICK_SECONDS)


def start():
    """Runs only in the process that owns the automation runner lock."""
    global _THREAD
    if _THREAD and _THREAD.is_alive() or not runs.runner_active():
        return
    _STOP.clear()
    _THREAD = threading.Thread(target=_loop, daemon=True, name="cora-automation-schedule")
    _THREAD.start()


def stop():
    _STOP.set()
    if _THREAD:
        _THREAD.join(timeout=2)
