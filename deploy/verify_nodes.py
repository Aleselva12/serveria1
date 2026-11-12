"""Bounded functional checks. Run inside the installed API container.

python -m deploy.verify_nodes --persist --output /state/node-verification.json
Only generated fixtures are written. No user service is restarted.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from uuid import UUID, uuid4

from core.additional_verifications import DIRECT
from core.additional_verifications import REGRESSIONS as EXTRA_REGRESSIONS

REGRESSIONS = {
    "memory_regression": ("tests.test_memory_context.ContextContractTests", "tests.test_context_contracts"),
    "calendar_regression": ("tests.test_google_calendar", "tests.test_google_calendar_approvals.GoogleCalendarApprovalTests"),
    "orchestration_regression": ("tests.test_system_coordinator", "tests.test_error_decisions"),
    "files_regression": ("tests.test_library_writes", "tests.test_file_editor"),
}
REGRESSIONS.update(EXTRA_REGRESSIONS)
CHECKS = ("memory_e2e", "calendar_e2e", "desktop_e2e", "laptop_e2e", "worker_e2e", "debian_host_e2e", "systemd_host_e2e", "host_admin_e2e", *REGRESSIONS, *DIRECT)
ROOT = Path(__file__).resolve().parents[1]


def _child(action, run_id, timeout=90, settings=None):
    result = subprocess.run([sys.executable, "-m", "deploy.verify_nodes",
                             "--action", action, "--run-id", run_id], cwd=ROOT,
                            env={**os.environ, **(settings or {}), "CORA_EMBEDDING_MODEL": "",
                                 "CORA_VERIFICATION_SYNTHETIC": "1" if action in REGRESSIONS or action in DIRECT or action == "worker_e2e" else os.getenv("CORA_VERIFICATION_SYNTHETIC", "0")},
                            capture_output=True, text=True, timeout=timeout)
    # Library logging must not enter public evidence or expose credentials.
    for line in reversed(result.stdout.splitlines()):
        if line.startswith("CORA_CHECK="):
            return json.loads(line[len("CORA_CHECK="):])
    raise RuntimeError("Controllo senza risultato")


def _calendar_ready():
    test = os.getenv("CORA_VERIFY_CALENDAR_TOKEN_PATH", "").strip()
    production = os.getenv("CORA_GOOGLE_CALENDAR_TOKEN_PATH", "/state/google-calendar/token.json")
    return (os.getenv("CORA_VERIFY_CALENDAR_TEST_ACCOUNT") == "yes" and test
            and Path(test).resolve() != Path(production).resolve() and Path(test).is_file())


def _calendar_provider():
    # Must happen before importing the provider. Only a separate test account.
    if not _calendar_ready():
        raise ValueError("Account Google di collaudo separato richiesto")
    os.environ["CORA_GOOGLE_CALENDAR_TOKEN_PATH"] = os.environ["CORA_VERIFY_CALENDAR_TOKEN_PATH"]
    from core.domain import google_calendar
    return google_calendar


def _action(action, run_id):
    token = str(UUID(run_id))
    key = "cora-verification-" + token
    if action in DIRECT:
        state, detail = DIRECT[action]()
        return {"status": state, "detail": detail}
    if action in {"debian_host_e2e", "systemd_host_e2e", "host_admin_e2e"}:
        from programmer_agent import releases
        try:
            snapshot = releases.request("GET", "/host/diagnostics", timeout=20)
        except ValueError:
            return {"status": "unknown", "detail": "Diagnostica host non disponibile: aggiornare/avviare il bridge updater sul Debian"}
        if action == "debian_host_e2e":
            os_info = snapshot.get("os") or {}
            identity = snapshot.get("identity") or {}
            packages = snapshot.get("packages") or {}
            dpkg = packages.get("dpkg") or {}
            upgrades = packages.get("upgrades") or {}
            if os_info.get("ID") != "debian":
                return {"status": "fail", "detail": "Host updater non identificato come Debian"}
            if not identity.get("uidMatchesConfigured") or not identity.get("privateUpdaterFiles"):
                return {"status": "fail", "detail": "UID/GID updater o permessi dei file privati host non coerenti"}
            if not dpkg.get("available") or not dpkg.get("auditClean"):
                return {"status": "fail", "detail": "Database pacchetti Debian non integro o non verificabile"}
            if not upgrades.get("available") or upgrades.get("simulationOk") is not True:
                return {"status": "unknown", "detail": "Simulazione aggiornamenti APT non disponibile; nessun pacchetto modificato"}
            pending = upgrades.get("pending")
            if pending:
                return {"status": "unknown", "detail": f"Debian coerente; {pending} aggiornamenti risultano pendenti dalla cache APT"}
            return {"status": "pass", "detail": "Debian reale verificato: identità host, UID/GID updater, file privati, dpkg e APT senza aggiornamenti pendenti"}
        units = snapshot.get("systemd") or {}
        if action == "systemd_host_e2e":
            unit = units.get("cora-updater.service") or {}
            ok = (
                unit.get("available") and unit.get("loadState") == "loaded" and
                unit.get("activeState") == "active" and unit.get("subState") == "running" and
                str(unit.get("execMainStatus", "")) == "0" and unit.get("fragmentPresent") and
                bool(unit.get("standardOutput")) and bool(unit.get("standardError"))
            )
            return {
                "status": "pass" if ok else "fail",
                "detail": (
                    "cora-updater.service caricato e attivo; stato processo e sink output systemd leggibili. Nessun restart eseguito"
                    if ok else "cora-updater.service non risulta pienamente attivo/coerente sul Debian"
                ),
            }
        ssh = units.get("ssh.service") or {}
        updater = units.get("cora-updater.service") or {}
        ok = (
            ssh.get("available") and ssh.get("loadState") == "loaded" and
            ssh.get("activeState") == "active" and ssh.get("fragmentPresent") and
            updater.get("fragmentPresent")
        )
        return {
            "status": "pass" if ok else "fail",
            "detail": (
                "ssh.service reale attivo e unità SSH/updater presenti; nessuna connessione SSH o lettura credenziali eseguita"
                if ok else "SSH o configurazione delle unità host non risultano disponibili/attivi"
            ),
        }
    if action == "worker_e2e":
        from core.agent_models import binding, chat_on_worker
        selected = binding("supervisor")
        if not selected or selected["machine_id"] == "local":
            return {"status": "unknown", "detail": "Il Supervisor usa il server: assegna il worker in Architettura per collaudare la chat remota"}
        challenge = "CORA_" + token.replace("-", "")
        response = chat_on_worker(selected["machine_id"], selected["model"], {
            "messages": [{"role":"user", "content":"Ripeti esattamente questo codice, senza altro testo: " + challenge}],
            "options":{"temperature":0, "num_predict":96}})
        from core.model_evidence import matches_requested
        message = response.get("message") if isinstance(response, dict) else None
        if (not isinstance(response, dict) or response.get("done") is not True or
                matches_requested(selected["model"], response.get("model")) is not True or
                not isinstance(message, dict) or message.get("role") != "assistant" or
                message.get("tool_calls") or not isinstance(message.get("content"), str) or message["content"].strip() != challenge):
            return {"status":"fail", "detail":"Worker raggiunto, ma prova funzionale non valida: codice, modello o completamento non corrispondono. Non basta la connessione."}
        return {"status":"pass", "detail":"Worker assegnato: codice univoco della richiesta restituito correttamente, modello effettivo e completamento verificati. GPU e qualità generale escluse"}
    if action in REGRESSIONS:
        import io
        import unittest
        sys.path.insert(0, str(ROOT / "tests"))
        suite = unittest.defaultTestLoader.loadTestsFromNames(REGRESSIONS[action])
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        state = "fail" if not result.wasSuccessful() else "skipped" if result.skipped or not result.testsRun else "pass"
        return {"status": state, "detail": f"Regressioni isolate: {result.testsRun} test, {len(result.failures)} fallimenti, {len(result.errors)} errori, {len(result.skipped)} saltati. Servizi reali non certificati"}
    if action == "memory_write":
        from core.domain.memory import save_memory
        save_memory(memory_type="note", key=key, content=key,
                    source="verification", importance=1)
        return {"status": "pass"}
    if action == "memory_read":
        from core.domain.memory import search_memories
        rows = search_memories(key, memory_type="note")
        if not any(row["key"] == key and row["content"] == key for row in rows):
            raise ValueError("Memoria non riletta")
        return {"status": "pass"}
    if action == "memory_cleanup":
        from core.infra.database import db_connection
        # Generated key AND source: never delete an unrelated memory.
        with db_connection(ensure_schema=False) as conn:
            conn.execute("DELETE FROM memories WHERE key=%s AND source='verification'", (key,))
        return {"status": "pass"}
    if action.startswith("calendar_"):
        calendar = _calendar_provider()
        event_id = calendar._local_google_id("manual:" + key)
        from googleapiclient.errors import HttpError
        if action == "calendar_cleanup":
            try:
                calendar.service().events().delete(calendarId="primary", eventId=event_id,
                                                   sendUpdates="none").execute()
            except HttpError as error:
                if error.resp.status not in (404, 410):
                    raise
            return {"status": "pass"}
        start = datetime.now(UTC) + timedelta(days=1)
        data = dict(title=key, start=start.isoformat(), end=(start+timedelta(minutes=5)).isoformat(),
                    all_day=False, notes="Collaudo automatico Cora", reminder_minutes=None)
        first = calendar.create_event(data, request_id=key)
        second = calendar.create_event(data, request_id=key)
        if first["id"] != event_id or second["id"] != event_id:
            raise ValueError("Idempotenza non rispettata")
        changed = calendar.update_event(event_id, {**data, "title": key+" updated"},
                                        expected_version=second["version"])
        if calendar.get_event(event_id)["title"] != key+" updated":
            raise ValueError("Modifica non riletta")
        calendar.delete_event(event_id, expected_version=changed["version"])
        try:
            remaining = calendar.service().events().get(calendarId="primary", eventId=event_id).execute()
        except HttpError as error:
            if error.resp.status not in (404, 410):
                raise
        else:
            if remaining.get("status") != "cancelled":
                raise ValueError("Evento non eliminato")
        return {"status": "pass", "detail": "OAuth test: creazione, duplicato, modifica, lettura e cancellazione; approvazioni UI non collaudate"}
    if action in ("desktop_e2e", "laptop_e2e"):
        from core.api.machines_api import _find, _settings, test_worker_inference
        machine_id = os.getenv("CORA_VERIFY_" + action.split("_")[0].upper() + "_ID", "").strip()
        if not machine_id:
            return {"status": "unknown", "detail": "Seleziona la macchina nelle destinazioni dei collaudi"}
        machine = _find(machine_id)
        settings = _settings(machine)
        if not settings["enabled"] or not settings["selected_model"]:
            return {"status": "skipped", "detail": "Worker disattivato o modello non selezionato"}
        response = test_worker_inference(machine_id)
        # Match the backend-reported model, not merely the requested name.
        expected = settings["selected_model"]
        from core.model_evidence import matches_requested
        actual = response.get("actual_model")
        if not isinstance(actual, str):
            return {"status": "unknown", "detail": "Worker precedente: aggiornare per verificare il modello effettivo"}
        if matches_requested(expected, actual) is not True or not response.get("done"):
            raise ValueError("Modello effettivo diverso o generazione incompleta")
        if "CORA_WORKER_OK" not in response.get("response", ""):
            raise ValueError("Risposta campione non valida")
        return {"status": "pass", "detail": "Inferenza completata sulla macchina configurata; modello effettivo corrispondente. Utilizzo GPU non certificato"}
    raise ValueError("Azione non prevista")


def available_checks():
    """Discover executable checks server-side; the website never embeds this list."""
    from core.verify.project_checks import _PROBES
    return tuple(dict.fromkeys((*_PROBES, *CHECKS)))


def run(check_id, settings=None):
    from core.verify.project_checks import _PROBES
    if check_id in _PROBES:
        try:
            state, detail = _PROBES[check_id]()
            if state not in {"pass", "fail", "unknown", "skipped"}:
                raise ValueError("Invalid state")
            return {"status": state, "detail": str(detail)[:240]}
        except Exception:
            return {"status": "fail", "detail": "Controllo non riuscito: " + check_id}
    run_id = str(uuid4())
    cleanup = None
    if check_id == "calendar_e2e" and not _calendar_ready():
        return {"status": "unknown", "detail": "Account Google di prova non collegato; il calendario reale non è stato usato"}
    if check_id == "memory_e2e" and not os.getenv("CORA_DATABASE_URL", "").strip():
        return {"status": "unknown", "detail": "Database non configurato"}
    try:
        if check_id == "memory_e2e":
            cleanup = "memory_cleanup"
            first = _child("memory_write", run_id)
            result = _child("memory_read", run_id) if first.get("status") == "pass" else first
            result["detail"] = ("Memoria scritta e riletta da un nuovo processo; embeddings e riavvio del servizio non collaudati"
                                if result.get("status") == "pass" else "Memoria non riletta dal nuovo processo")
        else:
            cleanup = "calendar_cleanup" if check_id == "calendar_e2e" else None
            result = _child("calendar_check" if cleanup else check_id, run_id,
                            timeout=330 if check_id in ("desktop_e2e", "laptop_e2e", "worker_e2e") else 120, settings=settings)
    except subprocess.TimeoutExpired:
        result = {"status": "fail", "detail": "Tempo massimo del collaudo superato; ID " + run_id}
    except Exception:
        result = {"status": "fail", "detail": "Collaudo non riuscito: " + check_id}
    finally:
        if cleanup:
            try:
                cleaned = _child(cleanup, run_id, timeout=45)
                if cleaned.get("status") != "pass":
                    raise RuntimeError("Cleanup fallito")
            except Exception:
                # A failed cleanup must also fail the check; fixture ID permits recovery.
                result = {"status": "fail", "detail": "Pulizia fixture non riuscita; ID collaudo " + run_id}
    return result


@contextmanager
def _lease(persist):
    if not persist:
        yield
        return
    import psycopg
    # Session lock, no transaction held while inference or remote checks run.
    with psycopg.connect(os.environ.get("CORA_DATABASE_URL", ""), connect_timeout=5,
                         autocommit=True, options="-c statement_timeout=5000") as conn:
        if not conn.execute("SELECT pg_try_advisory_lock(709241010)").fetchone()[0]:
            raise RuntimeError("Una suite di collaudo è già in corso")
        try:
            yield
        finally:
            conn.execute("SELECT pg_advisory_unlock(709241010)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checks", nargs="+", choices=CHECKS, default=list(CHECKS))
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--action", choices=(*CHECKS, "memory_write", "memory_read", "memory_cleanup", "calendar_check", "calendar_cleanup"), help=argparse.SUPPRESS)
    parser.add_argument("--run-id", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.action:
        try:
            result = _action(args.action, args.run_id)
        except Exception:
            result = {"status": "fail", "detail": "Passaggio non riuscito: " + args.action}
        print("CORA_CHECK=" + json.dumps(result))
        return 0 if result["status"] == "pass" else 1
    try:
        with _lease(args.persist):
            return execute(args)
    except Exception:
        print("Suite non registrata: verificare connessione al registro o altra esecuzione in corso.", file=sys.stderr)
        return 3


def execute(args, on_result=None):
    from core.infra.release_identity import revision
    commit = revision()
    environment = "ci-verifier" if os.getenv("GITHUB_ACTIONS") == "true" else "debian-verifier" if sys.platform == "linux" and os.getenv("CORA_RUNTIME_MODE") == "server" else "local-verifier"
    rows = []
    for check_id in args.checks:
        start = monotonic()
        result = run(check_id, getattr(args, "settings", None))
        row = {"id": check_id, **result, "commit": commit or None, "environment": environment,
               "source": "manual", "at": datetime.now(UTC).isoformat(),
               "durationMs": int((monotonic()-start)*1000)}
        rows.append(row)
        if on_result:
            on_result(row)
        print(check_id + ": " + result["status"] + " · " + result.get("detail", ""))
    persisted = False
    if args.persist:
        from core.infra.database import db_connection
        # No schema changes; use the application's existing result store.
        with db_connection(ensure_schema=False) as conn:
            for row in rows:
                conn.execute("""INSERT INTO project_health_results
                    (check_id,status,detail,source,environment,commit_sha,duration_ms,observed_at)
                    VALUES (%s,%s,%s,'manual',%s,%s,%s,%s)""",
                    (row["id"], row["status"], row.get("detail", "")[:240], environment,
                     commit, row["durationMs"], row["at"]))
        persisted = True
    report = {"commit": commit or None, "environment": environment, "persisted": persisted, "checks": rows}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if any(row["status"] == "fail" for row in rows) else 2 if any(row["status"] != "pass" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
