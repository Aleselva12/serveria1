"""Background mail summaries: one at a time, nightly plus on demand.

The summary can take tens of minutes on a CPU-only server, so it never runs inside an
HTTP request. The page queues a job and reads the latest result; a nightly run
summarizes yesterday's mail for all accounts while nobody is using Cora.
"""
import fcntl
import json
import os
import tempfile
import threading
from datetime import UTC, datetime, timedelta

from core.domain import mail

STATUSES_DONE = ("ready", "partial", "empty", "unavailable", "failed")
_LOCK = threading.RLock()
_WAKE = threading.Event()
_STOP = threading.Event()
_THREAD = None
_PENDING = None
_RUNNER_LOCK = None  # open file holding the cross-process runner lock


def _directory():
    return mail.directory() / "summaries"


def _latest_path():
    return _directory() / "latest.json"


def _nightly_path():
    return _directory() / "nightly.json"


def _runner_lock_path():
    return _directory() / "runner.lock"


def nightly_window_hours():
    try:
        return max(1, min(23, int(os.getenv("CORA_MAIL_SUMMARY_WINDOW_HOURS", "4"))))
    except ValueError:
        return 4


def nightly_time():
    raw = os.getenv("CORA_MAIL_SUMMARY_TIME", "03:00").strip()
    try:
        hour, minute = (int(part) for part in raw.split(":"))
        if 0 <= hour < 24 and 0 <= minute < 60:
            return hour, minute
    except ValueError:
        pass
    return 3, 0


def _now():
    return datetime.now(UTC)


def _write(path, value):
    _directory().mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=_directory(), prefix=".summary-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def latest():
    hour, minute = nightly_time()
    with _LOCK:
        job = _read(_latest_path())
        pending = dict(_PENDING) if _PENDING else None
    return {"job": job, "pending": pending, "nightly": {"time": f"{hour:02d}:{minute:02d}", "timezone": "Europe/Rome",
                                                        "selection": "all", "scope": "yesterday"}}


def enqueue(selection, scope, trigger="manual"):
    """Queue one summary. A running or already queued job is never duplicated."""
    global _PENDING
    if _RUNNER_LOCK is None:
        raise ValueError("Riepilogo non disponibile: il servizio in background non è attivo in questo processo.")
    if selection != "all":
        mail.account_email(selection)
    with _LOCK:
        current = _read(_latest_path())
        if current and current.get("status") == "running":
            return {"accepted": False, "reason": "running", **latest()}
        if _PENDING:
            return {"accepted": False, "reason": "queued", **latest()}
        _PENDING = {"selection": selection, "scope": scope, "trigger": trigger, "queued_at": _now().isoformat()}
    _WAKE.set()
    return {"accepted": True, **latest()}


def run_job(job):
    started = _now().isoformat()
    record = {**job, "status": "running", "started_at": started, "finished_at": None, "summary": None}
    with _LOCK:
        _write(_latest_path(), record)
    try:
        result = mail.summarize(job["selection"], job["scope"])
        record.update(status=result.get("status", "unavailable"), summary=result.get("summary"),
                      notice=result.get("notice"), coverage=result.get("coverage"),
                      summarized_count=result.get("summarized_count", 0),
                      message_count=len(result.get("messages", [])),
                      errors=sorted(result.get("errors", {})))
    except Exception as error:
        # Only the error class is stored: no tokens, addresses or mail content.
        record.update(status="failed", notice="Riepilogo non completato (" + type(error).__name__ + ").")
    record["finished_at"] = _now().isoformat()
    with _LOCK:
        _write(_latest_path(), record)
    if record["status"] in ("ready", "partial"):
        _notify(record)
    return record


def _notify(record):
    try:
        from core.domain import notifications
        payload = {"title": "Cora · Mail", "body": "Riepilogo email pronto.", "url": "/#mail",
                   "tag": "mail-summary-" + record["finished_at"][:10]}
        for subscription in notifications._active_subscriptions():
            notifications.send_one(subscription, payload, ttl=43200)
    except Exception as error:
        # The summary is saved either way; only the push notice is lost.
        from core.infra.logging import report_swallowed_error
        report_swallowed_error("mail_summary_notify", error, component="mail_summary")


def _nightly_due(now_local):
    """Due once per day, only inside the night window (default 03:00-07:00).

    A restart during the day must not start a long CPU-bound summary while Cora is in use.
    """
    hour, minute = nightly_time()
    start = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if not start <= now_local < start + timedelta(hours=nightly_window_hours()):
        return False
    done = _read(_nightly_path()) or {}
    return done.get("day") != now_local.date().isoformat()


def _take_pending():
    global _PENDING
    with _LOCK:
        job, _PENDING = _PENDING, None
    return job


def _loop():
    while not _STOP.is_set():
        try:
            now_local = _now().astimezone(mail.ROME)
            if _nightly_due(now_local) and any(mail.token_path(key).is_file() for key in mail.ACCOUNTS):
                # A manual job already queued delays the nightly run to the next pass.
                if enqueue("all", "yesterday", trigger="nightly")["accepted"]:
                    _write(_nightly_path(), {"day": now_local.date().isoformat()})
            job = _take_pending()
            if job:
                run_job(job)
                continue
        except Exception as error:
            # Keep the worker alive; a failure here must not silently stop summaries.
            from core.infra.logging import report_swallowed_error
            report_swallowed_error("mail_summary_cycle", error, component="mail_summary")
        _WAKE.wait(60)
        _WAKE.clear()


def _recover_interrupted():
    current = _read(_latest_path())
    if current and current.get("status") == "running":
        current.update(status="failed", finished_at=_now().isoformat(),
                       notice="Riepilogo interrotto dal riavvio del server.")
        _write(_latest_path(), current)


def _acquire_runner_lock():
    """Only one process per state directory runs jobs.

    Post-update verification and tests can import the app inside the live container;
    without this lock they would mark the real running job as interrupted or start a
    second summary on the same Ollama.
    """
    global _RUNNER_LOCK
    try:
        _directory().mkdir(parents=True, exist_ok=True, mode=0o700)
        handle = open(_runner_lock_path(), "a+")
    except OSError:
        return False
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return False
    _RUNNER_LOCK = handle
    return True


def _release_runner_lock():
    global _RUNNER_LOCK
    if _RUNNER_LOCK is not None:
        try:
            fcntl.flock(_RUNNER_LOCK, fcntl.LOCK_UN)
        finally:
            _RUNNER_LOCK.close()
            _RUNNER_LOCK = None


def start():
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return
    if _RUNNER_LOCK is None and not _acquire_runner_lock():
        return
    try:
        _recover_interrupted()
    except OSError:
        pass
    _STOP.clear()
    _THREAD = threading.Thread(target=_loop, daemon=True, name="cora-mail-summary")
    _THREAD.start()


def stop():
    _STOP.set()
    _WAKE.set()
    if _THREAD:
        _THREAD.join(timeout=2)
    if not (_THREAD and _THREAD.is_alive()):
        _release_runner_lock()
