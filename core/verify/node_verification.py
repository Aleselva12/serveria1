"""Owner-only one-shot verification. GET never launches checks or model calls."""
from datetime import UTC, datetime
import os
import re
from threading import Event, Lock, Thread
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from core.access import owner_dependency
from core.health_catalog import CATALOG
from deploy import verify_nodes

router = APIRouter(prefix="/api/v1/system/node-verification", tags=["Node verification"],
                   dependencies=[Depends(owner_dependency("runtime"))])
LOCK_ID = 709241010  # Shared with the CLI; prevents overlapping website/CLI suites.


class Launch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    desktopMachineId: UUID | None = None
    laptopMachineId: UUID | None = None


def _now():
    return datetime.now(UTC).isoformat()


def _connection():
    import psycopg
    from psycopg.rows import dict_row

    from core.infra.database import DATABASE_URL
    if not DATABASE_URL:
        raise RuntimeError("Database non configurato")
    return psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row,
                           connect_timeout=5, options="-c statement_timeout=5000")


def _latest(conn):
    row = conn.execute("SELECT snapshot FROM node_verification_runs ORDER BY created_at DESC LIMIT 1").fetchone()
    return row["snapshot"] if row else None


def _save(conn, job):
    from psycopg.types.json import Jsonb
    conn.execute("UPDATE node_verification_runs SET snapshot=%s WHERE id=%s", (Jsonb(job), job["id"]))


def _locked(conn):
    return conn.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (LOCK_ID,)).fetchone()["acquired"]


def _release(conn):
    conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))


def _run(conn, job, settings):
    """Own the session lock until the last check and its evidence are stored."""
    try:
        from core.host_maintenance import ensure
        job["detail"] = "Verifica e allineamento prerequisiti updater host."
        _save(conn, job)
        job["hostMaintenance"] = ensure()
        _save(conn, job)
        def record(row):
            # Update the map and progress in one transaction after each check.
            next_job = {**job, "results": [*job["results"], row],
                        "completed": len(job["results"]) + 1, "updatedAt": _now()}
            next_job["currentCheck"] = job["checks"][next_job["completed"]] if next_job["completed"] < job["total"] else None
            with conn.transaction():
                conn.execute("""INSERT INTO project_health_results
                    (check_id,status,detail,source,environment,commit_sha,duration_ms,observed_at)
                    VALUES (%s,%s,%s,'manual',%s,%s,%s,%s)""",
                    (row["id"], row["status"], row.get("detail", "")[:240], row["environment"],
                     row["commit"] or "", row["durationMs"], row["at"]))
                _save(conn, next_job)
            job.update(next_job)
        verify_nodes.execute(SimpleNamespace(checks=job["checks"], persist=False, output=None, settings=settings), on_result=record)
        job["status"] = "failed" if any(r["status"] == "fail" for r in job["results"]) else "completed"
        job["detail"] = "Collaudi terminati. I controlli senza prerequisiti restano non verificati."
    except Exception:
        job["status"] = "interrupted"
        job["detail"] = "Esecuzione interrotta. Gli esiti giÃ  registrati restano disponibili; puoi riprovare."
        if "hostMaintenance" not in job:
            job["detail"] = "Prerequisito updater non pronto: controlla installazione e stato host-maintenance. Nessun collaudo eseguito."
    finally:
        job["currentCheck"] = None
        job["updatedAt"] = _now()
        try:
            _save(conn, job)
        finally:
            try:
                _release(conn)
            finally:
                conn.close()


@router.get("")
def status():
    try:
        with _connection() as conn:
            job = _latest(conn)
            if job and job["status"] == "running" and _locked(conn):
                try:
                    # The owning process exited/restarted. Never invent a pass.
                    job["status"] = "interrupted"
                    job["currentCheck"] = None
                    job["updatedAt"] = _now()
                    job["detail"] = "Il processo Ã¨ stato riavviato o interrotto. Puoi avviare un nuovo collaudo."
                    _save(conn, job)
                finally:
                    _release(conn)
        available = verify_nodes.available_checks()
        from core.verify.test_inventory import inventory
        test_inventory = inventory()
        return {"run": job,
                "availableChecks": [{"id": key, "title": CATALOG[key]["title"]} for key in available],
                "unavailableChecks": [{"id": key, "title": item["title"]} for key, item in CATALOG.items() if key not in available],
                "testInventory": test_inventory}
    except Exception:
        raise HTTPException(503, "Collaudi non disponibili: verifica il database e l'aggiornamento del server.") from None


@router.post("", status_code=202)
def start(body: Launch | None = None):
    return _launch(body, "manual")


def _installed_release():
    from core.verify.project_checks import _release
    release = (_release() or "").strip().lower()
    return release if re.fullmatch(r"[0-9a-f]{40}", release) else ""


def _launch(body: Launch | None, trigger: str):
    conn = None
    acquired = False
    try:
        body = body or Launch()
        settings = {}
        for name, identifier in (("DESKTOP", body.desktopMachineId), ("LAPTOP", body.laptopMachineId)):
            if identifier:
                from core.api.machines_api import _find
                _find(str(identifier))  # Only registered machines, never a client-provided URL/command.
                settings["CORA_VERIFY_" + name + "_ID"] = str(identifier)
        conn = _connection()
        acquired = _locked(conn)
        if not acquired:
            raise HTTPException(409, "Un collaudo Ã¨ giÃ  in corso. Attendi il risultato senza avviarne un altro.")
        from psycopg.types.json import Jsonb
        checks = list(verify_nodes.available_checks())
        job = {"id": str(uuid4()), "status": "running", "createdAt": _now(), "updatedAt": _now(),
               "checks": checks, "targets": body.model_dump(mode="json"), "currentCheck": checks[0] if checks else None,
               "total": len(checks), "completed": 0, "results": [], "trigger": trigger, "release": _installed_release(),
               "detail": "Collaudi avviati automaticamente dopo l'installazione." if trigger == "auto" else "Collaudi avviati sul server."}
        conn.execute("INSERT INTO node_verification_runs (id,snapshot) VALUES (%s,%s)", (job["id"], Jsonb(job)))
        # Return an independent snapshot: the worker may already be recording progress.
        response = {**job, "results": []}
        Thread(target=_run, args=(conn, job, settings), daemon=True, name="cora-node-verification").start()
        conn = None  # Ownership transferred to the worker, including lock release.
        return response
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Impossibile avviare i collaudi: verifica il database e l'aggiornamento del server.") from None
    finally:
        if conn is not None:
            try:
                if acquired:
                    _release(conn)
            finally:
                conn.close()


# Automatic run once per installed release, so a fresh install is verified
# without a click. Same runner, lock and evidence as the owner's button.
AUTO_DELAY_SECONDS = 180
_AUTO_STOP = Event()
_AUTO_LOCK = Lock()
_AUTO_THREAD = None


def auto_verify_release():
    """Start the suite unless this release already has a run. Returns the reason."""
    if os.getenv("CORA_AUTO_VERIFY", "1").strip() == "0":
        return "disabled"
    from core.verify.project_checks import _environment
    release = _installed_release()
    if _environment() != "debian-api" or not release:
        return "not_installed_release"
    with _connection() as conn:
        if conn.execute("SELECT 1 FROM node_verification_runs WHERE snapshot->>'release'=%s LIMIT 1", (release,)).fetchone():
            return "already_verified"
        previous = _latest(conn) or {}
    # Reuse the owner's last machine choice; an unregistered machine falls back to none.
    targets = {k: v for k, v in (previous.get("targets") or {}).items() if k in Launch.model_fields and v}
    for body in (Launch(**targets), Launch()) if targets else (Launch(),):
        try:
            _launch(body, "auto")
            return "started"
        except HTTPException as error:
            if error.status_code == 409:
                return "busy"
            if error.status_code != 404:
                raise
    return "not_started"


def _auto_loop():
    if _AUTO_STOP.wait(AUTO_DELAY_SECONDS):
        return
    try:
        auto_verify_release()
    except Exception:
        pass  # Never affect the API; the owner can still start it from the tree.


def start_auto():
    global _AUTO_THREAD
    with _AUTO_LOCK:
        if _AUTO_THREAD is not None and _AUTO_THREAD.is_alive():
            return
        _AUTO_STOP.clear()
        _AUTO_THREAD = Thread(target=_auto_loop, name="cora-auto-verification", daemon=True)
        _AUTO_THREAD.start()


def stop_auto():
    _AUTO_STOP.set()
