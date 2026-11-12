"""Metadata-only health evidence from completed real operations, never from a click."""
import os
import threading
from time import monotonic

_lock = threading.Lock()
_last = {}


def enabled():
    try:
        from core.database import DATABASE_URL
        from core.verify.project_checks import _release
        return bool(DATABASE_URL and _release() and os.getenv("GITHUB_ACTIONS") != "true" and os.getenv("CORA_VERIFICATION_SYNTHETIC") != "1")
    except Exception:
        return False


def record(check_id, status, detail):
    """Best effort: evidence storage must not turn a successful operation into an error."""
    try:
        from core.database import db_connection
        from core.verify.project_checks import _environment, _release
        if not enabled():
            return False
        commit = _release()
        if not commit:
            return False
        key = (check_id, commit)
        with _lock:
            previous = _last.get(key)
            if previous and previous[:2] == (status, detail) and monotonic() - previous[2] < 30:
                return True
            with db_connection(ensure_schema=False) as conn:
                conn.execute("""INSERT INTO project_health_results
                    (check_id,status,detail,source,environment,commit_sha,duration_ms)
                    VALUES (%s,%s,%s,'manual',%s,%s,0)""",
                    (check_id, status, ("Uso reale: " + detail)[:240], _environment(), commit))
            _last[key] = (status, detail, monotonic())
            if len(_last) > 200:
                _last.clear()
        return True
    except Exception:
        return False


def worker_ids(machine_id):
    """Use explicit saved targets; never infer desktop/laptop from a display name."""
    if not enabled():
        return []
    targets = {"desktopMachineId": os.getenv("CORA_VERIFY_DESKTOP_ID"),
               "laptopMachineId": os.getenv("CORA_VERIFY_LAPTOP_ID")}
    try:
        from core.database import db_connection
        with db_connection(ensure_schema=False) as conn:
            row = conn.execute("SELECT snapshot FROM node_verification_runs ORDER BY created_at DESC LIMIT 1").fetchone()
        if row:
            targets.update({k:v for k,v in row["snapshot"].get("targets", {}).items() if v})
    except Exception:
        pass
    return [name + "_e2e" for name in ("desktop", "laptop") if targets.get(name + "MachineId") == machine_id]


def worker_reply(machine_id, model, response, *, chat):
    from core.model_evidence import matches_requested
    reported = response.get("model") if chat else response.get("actual_model")
    match = matches_requested(model, reported)
    message = response.get("message")
    output = (isinstance(message, dict) and message.get("role") == "assistant"
              and bool(message.get("content") or message.get("tool_calls"))) if chat else bool(response.get("response"))
    status = "unknown" if match is None else "pass" if match and response.get("done") is True and output else "fail"
    detail = ("Chat agente sul worker; modello restituito e completamento verificati" if chat else
              "Inferenza /generate sul worker; modello restituito e completamento verificati")
    ids = list(worker_ids(machine_id))
    if chat:
        ids.append("worker_e2e")
    for check_id in ids:
        record(check_id, status, detail if status == "pass" else "Risposta worker non completa o modello effettivo non corrispondente")
    return status


def worker_failure(machine_id, *, chat=True):
    for check_id in (["worker_e2e"] if chat else []) + worker_ids(machine_id):
        record(check_id, "fail", "Chat sul worker assegnato non riuscita; nessun ripiego sul modello del server")


def calendar_write(action, result):
    """Only a provider mutation confirmed by a fresh provider read is evidence."""
    if not enabled():
        return
    try:
        from googleapiclient.errors import HttpError

        from core import google_calendar as calendar
        if action == "delete":
            try:
                current = calendar.service().events().get(calendarId="primary", eventId=result["id"]).execute()
            except HttpError as error:
                if error.resp.status not in (404, 410):
                    raise
            else:
                if current.get("status") != "cancelled":
                    record("calendar_e2e", "fail", "Cancellazione Google non confermata dalla rilettura")
                    return
        else:
            current = calendar.get_event(result["id"])
            if any(current.get(key) != result.get(key) for key in ("id", "version", "title", "start", "end")):
                record("calendar_e2e", "unknown", "Evento cambiato durante la rilettura; ripetere la verifica")
                return
        record("calendar_e2e", "pass", "Operazione Google " + action + " confermata con rilettura; idempotenza coperta dalle regressioni separate")
    except Exception:
        record("calendar_e2e", "unknown", "Operazione Google completata, ma rilettura non verificabile")
