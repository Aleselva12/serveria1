"""Background mail summaries: one at a time, nightly plus on demand.

The summary can take tens of minutes on a CPU-only server, so it never runs inside an
HTTP request. The page queues a job and reads the latest result; a nightly run
summarizes yesterday's mail for all accounts while nobody is using Cora.
"""
import json
import os
import tempfile
import threading
from datetime import datetime, UTC

from core.domain import mail

STATUSES_DONE = ("ready", "partial", "empty", "unavailable", "failed")
_LOCK = threading.RLock()
_WAKE = threading.Event()
_STOP = threading.Event()
_THREAD = None
_PENDING = None


def _directory():
    return mail.directory() / "summaries"


def _latest_path():
    return _directory() / "latest.json"


def _nightly_path():
    return _directory() / "nightly.json"


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
    except Exception:
        pass


def _nightly_due(now_local):
    hour, minute = nightly_time()
    if (now_local.hour, now_local.minute) < (hour, minute):
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
        except Exception:
            pass
        _WAKE.wait(60)
        _WAKE.clear()


def _recover_interrupted():
    current = _read(_latest_path())
    if current and current.get("status") == "running":
        current.update(status="failed", finished_at=_now().isoformat(),
                       notice="Riepilogo interrotto dal riavvio del server.")
        _write(_latest_path(), current)


def start():
    global _THREAD
    if _THREAD and _THREAD.is_alive():
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
