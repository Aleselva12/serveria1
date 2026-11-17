"""Alerts on health transitions: OK -> error -> restored.

Fed by every stored Debian result (periodic probes and collaudi). A periodic probe
must fail twice in a row before it counts, so a single slow answer is not an alert;
a collaudo runs once per night or install, so one failure is enough.

Each confirmed transition becomes an in-app notification (Home window and Notifiche
page). It is also pushed to the owner's devices, at most once every 6 hours per
check, and never between 23:00 and 07:00: those wait for one morning summary.
Notification text carries the check title and its stored detail, which are
already metadata-only; never exception messages or user content.
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.health_catalog import CATALOG

ROME = ZoneInfo("Europe/Rome")
PUSH_THROTTLE = timedelta(hours=6)
QUIET_HOURS = (23, 7)  # local [start, end): no push, morning summary instead
URL = "/#notifications"


def _now():
    return datetime.now(UTC)


def quiet(at: datetime) -> bool:
    hour = at.astimezone(ROME).hour
    start, end = QUIET_HOURS
    return hour >= start or hour < end


def confirmations(check_id: str, source: str) -> int:
    """Failures in a row needed before alerting."""
    return 2 if source == "periodic" and CATALOG.get(check_id, {}).get("automated") else 1


def transition(state: dict | None, status: str, needed: int, at: datetime) -> tuple[dict | None, str | None]:
    """Pure rule: next state and the event to notify ('failure', 'recovery' or None).

    warn/unknown/skipped results say nothing about the transition and are ignored.
    """
    if status not in {"pass", "fail"}:
        return state, None
    current = dict(state or {"state": "ok", "fail_streak": 0, "notified": False,
                             "changed_at": at, "last_alert_at": None})
    if status == "pass":
        event = "recovery" if current["state"] == "failing" and current["notified"] else None
        if current["state"] == "failing":
            current.update(state="ok", changed_at=at, notified=event is not None)
        current["fail_streak"] = 0
        return current, event
    current["fail_streak"] += 1
    if current["state"] == "ok" and current["fail_streak"] >= needed:
        last = current.get("last_alert_at")
        notify = last is None or at - last >= PUSH_THROTTLE
        current.update(state="failing", changed_at=at, notified=notify)
        if notify:
            current["last_alert_at"] = at
        return current, "failure" if notify else None
    return current, None


def _message(event, check_id, detail, commit):
    title = CATALOG.get(check_id, {}).get("title", check_id)
    version = (" · versione " + commit[:7]) if commit else ""
    if event == "failure":
        return "error", "Errore: " + title, (detail or "Controllo non superato")[:200] + version
    return "success", "Ripristinato: " + title, "Il controllo è di nuovo superato" + version


def create(conn, *, source, kind, severity, title, body="", url=URL, ref=None, commit="", at=None):
    identifier = str(uuid4())
    conn.execute("""INSERT INTO app_notifications
        (id,created_at,source,kind,severity,title,body,url,ref,commit_sha)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (identifier, at or _now(), source, kind, severity, title[:200], body[:500], url, ref, commit or ""))
    return identifier


def observe(results: list[dict], source: str) -> list[str]:
    """Update alert state for stored results; return the new notification ids.

    Never raises: alerting must not affect the stored evidence.
    """
    created = []
    try:
        from core.infra.database import db_connection
        with db_connection() as conn:
            for row in results:
                if not str(row.get("environment", "")).startswith("debian"):
                    continue  # CI, local or another machine: not the server's state
                check_id, at = row["id"], row.get("at") or _now()
                if isinstance(at, str):
                    at = datetime.fromisoformat(at)
                with conn.transaction():
                    stored = conn.execute("SELECT * FROM health_alert_state WHERE check_id=%s FOR UPDATE",
                                          (check_id,)).fetchone()
                    state, event = transition(dict(stored) if stored else None, row["status"],
                                              confirmations(check_id, source), at)
                    if state is None:
                        continue
                    if event:
                        severity, title, body = _message(event, check_id, row.get("detail", ""), row.get("commit", ""))
                        created.append(create(conn, source="health", kind=event, severity=severity, title=title,
                                              body=body, ref=check_id, commit=row.get("commit", ""), at=at))
                    conn.execute("""INSERT INTO health_alert_state
                        (check_id,state,fail_streak,notified,changed_at,last_alert_at) VALUES (%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (check_id) DO UPDATE SET state=EXCLUDED.state, fail_streak=EXCLUDED.fail_streak,
                        notified=EXCLUDED.notified, changed_at=EXCLUDED.changed_at, last_alert_at=EXCLUDED.last_alert_at""",
                        (check_id, state["state"], state["fail_streak"], state["notified"],
                         state["changed_at"], state.get("last_alert_at")))
    except Exception as error:
        from core.infra.logging import report_swallowed_error
        report_swallowed_error("health_alerts_observe", error, component="health_monitor")
    if created:
        wake()
    return created


def _push(payload, tag):
    from core.domain import notifications
    for subscription in notifications._active_subscriptions():
        notifications.send_one(subscription, {**payload, "url": URL, "tag": tag}, ttl=43200)


def deliver(now: datetime | None = None) -> int:
    """Push pending notifications; in quiet hours wait, then send one summary."""
    now = now or _now()
    if quiet(now):
        return 0
    from core.infra.database import db_connection
    with db_connection() as conn:
        # Claim before sending: with several API processes each row is pushed once.
        pending = conn.execute("""UPDATE app_notifications SET pushed_at=%s
            WHERE pushed_at IS NULL AND dismissed_at IS NULL AND source='health'
            RETURNING id,title,body,ref,created_at""", (now,)).fetchall()
    if not pending:
        return 0
    pending = sorted(pending, key=lambda row: row["created_at"])
    overnight = [row for row in pending if quiet(row["created_at"])]
    if len(overnight) > 1:
        _push({"title": "Cora · Collaudi della notte",
               "body": f"{len(overnight)} avvisi: " + "; ".join(r["title"] for r in overnight[:3])},
              "health-overnight")
        others = [row for row in pending if not quiet(row["created_at"])]
    else:
        others = pending
    for row in others:
        _push({"title": "Cora · " + row["title"], "body": row["body"]}, "health-" + (row["ref"] or "check"))
    return len(pending)


_WAKE = threading.Event()
_STOP = threading.Event()
_THREAD = None
_LOCK = threading.Lock()
TICK_SECONDS = 300


def wake():
    _WAKE.set()


def _loop():
    while not _STOP.is_set():
        try:
            deliver()
        except Exception as error:
            from core.infra.logging import report_swallowed_error
            report_swallowed_error("health_alerts_push", error, component="health_monitor")
        _WAKE.wait(TICK_SECONDS)
        _WAKE.clear()


def start():
    global _THREAD
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return
        _STOP.clear()
        _THREAD = threading.Thread(target=_loop, name="cora-health-alerts", daemon=True)
        _THREAD.start()


def stop():
    _STOP.set()
    _WAKE.set()
