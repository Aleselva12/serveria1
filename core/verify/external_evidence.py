"""CI GitHub and updater outcomes in the single health registry, as information.

Stored with source 'ci' / 'updater' and a non-Debian environment, so they never
colour the map green (only Debian results do) and never raise alerts: they show
what GitHub and the updater said about the installed version, next to the
collaudi. A row is written only when the outcome changes, or once a day so it
stays current. Nothing is sent to GitHub: one public, unauthenticated read.
"""
from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from urllib.request import Request, urlopen

REPOSITORY = "Aleselva12/serveria1"
CI_CHECK, UPDATER_CHECK = "ci_github", "updater_install"
ENVIRONMENTS = {CI_CHECK: "ci-github", UPDATER_CHECK: "updater-host"}
SOURCES = {CI_CHECK: "ci", UPDATER_CHECK: "updater"}
REFRESH = timedelta(hours=24)
TICK_SECONDS = 3600
LOCK_ID = 709241011
_OK = {"success", "neutral", "skipped"}
_BAD = {"failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale"}


def summarize_check_runs(runs: list[dict]) -> tuple[str, str]:
    """Outcome of the GitHub checks of one commit."""
    if not runs:
        return "unknown", "CI GitHub: nessun controllo registrato per la versione installata"
    pending = [r for r in runs if r.get("status") != "completed"]
    failed = sorted({r.get("name", "?") for r in runs if r.get("conclusion") in _BAD})
    passed = [r for r in runs if r.get("conclusion") in _OK]
    if failed:
        return "fail", ("CI GitHub: falliti " + ", ".join(failed))[:240]
    if pending:
        return "unknown", f"CI GitHub: {len(pending)} controlli ancora in corso, {len(passed)} superati"
    return "pass", f"CI GitHub: {len(passed)} controlli superati sulla versione installata"


def ci_evidence(commit: str, fetch=None) -> tuple[str, str]:
    fetch = fetch or _github
    try:
        data = fetch(f"https://api.github.com/repos/{REPOSITORY}/commits/{commit}/check-runs?per_page=100")
        return summarize_check_runs(data.get("check_runs", []))
    except Exception as error:
        return "unknown", "CI GitHub non raggiungibile: " + type(error).__name__


def _github(url):
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Cora-health"})
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read(2_000_000))


def updater_evidence(jobs: list[dict]) -> tuple[str, str, str]:
    """Latest finished installation or rollback: status, detail and its commit."""
    finished = [j for j in jobs if j.get("kind") in {"apply", "rollback"}
                and j.get("status") in {"completed", "failed", "recovery_required"}]
    if not finished:
        return "unknown", "Updater: nessuna installazione registrata", ""
    job = max(finished, key=lambda j: j.get("updated_at") or j.get("created_at") or "")
    action = "Installazione" if job["kind"] == "apply" else "Ripristino versione precedente"
    commit = job.get("commit") or ""
    when = (job.get("updated_at") or "")[:16].replace("T", " ")
    if job["status"] == "completed":
        return "pass", f"Updater: {action.lower()} di {commit[:7]} completata ({when} UTC)", commit
    stage = job.get("error_stage") or job.get("phase") or "sconosciuta"
    if job["status"] == "recovery_required":
        return "fail", f"Updater: {action.lower()} di {commit[:7]} richiede recupero manuale (fase {stage})", commit
    return "fail", f"Updater: {action.lower()} di {commit[:7]} fallita (fase {stage}); versione precedente mantenuta", commit


def collect(release: str) -> list[dict]:
    rows = []
    if release:
        status, detail = ci_evidence(release)
        rows.append({"id": CI_CHECK, "status": status, "detail": detail, "commit": release})
    try:
        from programmer_agent import releases
        state = releases.status()
        if state.get("available", True):
            status, detail, commit = updater_evidence(state.get("jobs", []))
            rows.append({"id": UPDATER_CHECK, "status": status, "detail": detail, "commit": commit})
    except Exception as error:
        rows.append({"id": UPDATER_CHECK, "status": "unknown", "commit": "",
                     "detail": "Updater non raggiungibile: " + type(error).__name__})
    return rows


def changed(previous, row, now) -> bool:
    if previous is None:
        return True
    same = (previous["status"], previous["detail"], previous["commit_sha"]) == (row["status"], row["detail"], row["commit"])
    return not same or now - previous["observed_at"] >= REFRESH


def record(now: datetime | None = None) -> int:
    """Store changed outcomes; return how many rows were written."""
    from core.infra.database import db_connection
    from core.verify.project_checks import _environment, _release
    if _environment() != "debian-api":
        return 0  # CI and development do not describe the installed server
    now = now or datetime.now(UTC)
    written = 0
    with db_connection() as conn:
        if not conn.execute("SELECT pg_try_advisory_xact_lock(%s) AS ok", (LOCK_ID,)).fetchone()["ok"]:
            return 0
        for row in collect(_release()):
            previous = conn.execute("""SELECT status,detail,commit_sha,observed_at FROM project_health_results
                WHERE check_id=%s ORDER BY observed_at DESC,id DESC LIMIT 1""", (row["id"],)).fetchone()
            if changed(previous, row, now):
                conn.execute("""INSERT INTO project_health_results
                    (check_id,status,detail,source,environment,commit_sha,duration_ms,observed_at)
                    VALUES (%s,%s,%s,%s,%s,%s,0,%s)""",
                    (row["id"], row["status"], row["detail"][:240], SOURCES[row["id"]],
                     ENVIRONMENTS[row["id"]], row["commit"], now))
                written += 1
    return written


_STOP = threading.Event()
_THREAD = None
_LOCK = threading.Lock()


def _loop():
    # First read shortly after start-up, when an installation has just finished.
    if _STOP.wait(120):
        return
    while not _STOP.is_set():
        try:
            record()
        except Exception as error:
            from core.infra.logging import report_swallowed_error
            report_swallowed_error("external_evidence", error, component="health_monitor")
        _STOP.wait(TICK_SECONDS)


def start():
    global _THREAD
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return
        _STOP.clear()
        _THREAD = threading.Thread(target=_loop, name="cora-external-evidence", daemon=True)
        _THREAD.start()


def stop():
    _STOP.set()
