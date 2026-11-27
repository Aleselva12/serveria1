"""Optional local, tool-free interpretation of diagnostic signals."""
import threading

LOCK = threading.Lock()
SIGNALS = {
    "Dipendenza non disponibile": ("no matching distribution", "notarget", "could not find a version"),
    "Compilazione o tipi": ("typescript", "error ts", "failed to compile"),
    "Connessione": ("connection refused", "could not resolve", "network is unreachable"),
    "Tempo scaduto": ("timeout", "timed out"),
    "Permessi": ("permission denied", "access denied"),
    "Spazio esaurito": ("no space left", "disk full"),
    "Migrazione dati": ("alembic", "migration"),
    "Test fallito": ("assertionerror", "test failed", "failed ("),
}
OPERATIONS = {"prepare": "preparazione", "apply": "installazione",
              "publish": "pubblicazione GitHub", "rollback": "ripristino"}
PHASES = {"building": "build", "testing": "test", "publishing": "GitHub",
          "backing_up": "backup", "migration_trial": "migrazione",
          "candidate_starting": "avvio del candidato", "restoring": "ripristino"}


def enabled():
    from core.models import resolve_model
    try:
        settings = resolve_model("update_diagnostics")
        return settings["machine_id"] == "local" and bool(settings["model"])
    except (OSError, RuntimeError, ValueError):
        return False


def facts(job):
    # Extract fixed labels only. Arbitrary logs can carry secrets or instructions.
    log = " ".join(str(job.get(key, "")) for key in ("error", "error_detail", "error_stage")).lower()
    return {
        "operazione": OPERATIONS.get(job.get("kind"), "aggiornamento"),
        "fase": PHASES.get(job.get("phase"), "sconosciuta"),
        "esito": "richiede ripristino" if job["status"] == "recovery_required" else "fallita",
        "segnali": [label for label, terms in SIGNALS.items() if any(term in log for term in terms)],
    }


def analyze(releases, job, retry=False):
    if not enabled() or not LOCK.acquire(blocking=retry):
        return
    try:
        path = f"/jobs/{job['id']}/error-analysis"
        if not releases.request("POST", path, {"retry": retry}, timeout=5)["claimed"]:
            return
        result = {"status": "unavailable", "summary": ""}
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            from core.models import get_chat_model
            model = get_chat_model("update_diagnostics", num_predict=450,
                                   client_kwargs={"timeout": 25, "trust_env": False})
            content = model.invoke([
                SystemMessage(content="Riassumi in italiano un errore dell'updater. Indica problema, "
                              "componente, possibili cause esplicitamente ipotetiche e impatto. "
                              "Se mancano informazioni dichiaralo. Non proporre azioni o comandi."),
                HumanMessage(content=str(facts(job))),
            ]).content
            if isinstance(content, str) and content.strip():
                result = {"status": "done", "summary": content.strip()[:2400]}
        except Exception:
            pass  # A missing or failed model has no effect on updater operations.
        releases.request("POST", path, result, timeout=5)
    except (OSError, ValueError, KeyError):
        pass
    finally:
        LOCK.release()
