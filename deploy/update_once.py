"""One-shot owner-driven update through the already installed Debian updater.

Requires the owner to have fast-forwarded the trusted checkout to main first.
Uses only the updater's fixed authenticated API, never host shell endpoints.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def api(root: Path, method: str, path: str, payload=None):
    config = json.loads((root / "config.json").read_text())
    listen = config["listen"]
    # The host service normally binds the docker bridge, not 127.0.0.1.
    if listen in ("0.0.0.0", "::", ""):
        listen = "127.0.0.1"
    if not re.fullmatch(r"[0-9a-fA-F:.]+", listen):
        raise RuntimeError("Indirizzo di ascolto updater non valido.")
    if ":" in listen:
        listen = "[" + listen + "]"
    token = (root / "bridge.token").read_text().strip()
    if not token:
        raise RuntimeError("Token updater assente.")
    url = "http://" + listen + ":" + str(int(config["port"])) + path
    request = Request(url, data=json.dumps(payload).encode() if method == "POST" else None,
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                      method=method)
    try:
        with urlopen(request, timeout=45) as response:
            return json.load(response)
    except HTTPError as error:
        try:
            detail = json.load(error).get("detail", "HTTP " + str(error.code))
        except (ValueError, AttributeError):
            detail = "HTTP " + str(error.code)
        raise RuntimeError(str(detail)) from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(
            "Comunicazione non confermata con l'updater. NON ripetere il comando senza controllare i job."
        ) from error


def wait_for(root: Path, job_id: str, expected: str, allowed: set[str], deadline: float):
    last = None
    while time.monotonic() < deadline:
        job = api(root, "GET", "/jobs/" + job_id)
        if job.get("commit") != expected:
            raise RuntimeError("Commit job diverso dalla versione verificata: aggiornamento interrotto.")
        signature = (job.get("status"), job.get("phase"))
        if signature != last:
            print("Updater:", job.get("kind"), job.get("status"), job.get("phase"), flush=True)
            last = signature
        if job.get("status") in allowed:
            return job
        if job.get("status") in {"failed", "recovery_required", "cancelled"}:
            raise RuntimeError("Aggiornamento non riuscito: " + str(job.get("error") or job.get("status")))
        time.sleep(5)
    raise RuntimeError("Tempo di attesa superato: il job può continuare sul server. NON ripetere automaticamente.")


def run(root: Path, expected: str):
    if not re.fullmatch("[a-f0-9]{40}", expected):
        raise RuntimeError("Commit Git completo non valido.")
    config = json.loads((root / "config.json").read_text())
    if config.get("api_target") != "api-audio-cpu":
        raise RuntimeError("Target updater non è api-audio-cpu; non sovrascrivere il profilo Audio.")
    status = api(root, "GET", "/status")
    if not status.get("available"):
        raise RuntimeError("Updater non disponibile.")
    if any(j.get("status") in {"queued", "running", "recovery_required"} for j in status.get("jobs", [])):
        raise RuntimeError("È già presente un job in corso o un ripristino necessario.")
    print("Commit attivo:", status.get("active_commit"), flush=True)
    print("Commit richiesto:", expected, flush=True)
    workspace = api(root, "POST", "/workspaces", {"title": "Aggiornamento Cora main verificato"})
    # This is a read-back of the trusted Git source selected by the host service.
    if workspace.get("source_commit") != expected:
        raise RuntimeError("GitHub main differisce dal commit atteso: nessun rilascio avviato.")
    saved = api(root, "POST", "/workspaces/" + workspace["id"] + "/commit",
                {"message": "Prepare current main for deployment"})
    if saved.get("commit") != expected:
        raise RuntimeError("Commit della copia preparata differente: nessun rilascio avviato.")
    print("Preparazione e test automatici…", flush=True)
    preparation = api(root, "POST", "/jobs",
                      {"kind": "prepare", "workspace_id": workspace["id"], "commit": expected})
    ready = wait_for(root, preparation["id"], expected, {"ready"}, time.monotonic() + 45 * 60)
    if ready.get("status") != "ready":
        raise RuntimeError("Rilascio non verificato: installazione negata.")
    print("Versione verificata. Avvio backup e installazione controllata…", flush=True)
    installation = api(root, "POST", "/jobs",
                       {"kind": "apply", "release_id": preparation["id"], "commit": expected})
    wait_for(root, installation["id"], expected, {"completed"}, time.monotonic() + 30 * 60)
    final = api(root, "GET", "/status")
    if final.get("active_commit") != expected:
        raise RuntimeError("Installazione terminata ma commit attivo non corrisponde: verifica necessaria.")
    print("AGGIORNAMENTO COMPLETATO:", expected, flush=True)


def main():
    parser = argparse.ArgumentParser(description="Aggiorna Cora tramite il servizio host indipendente.")
    parser.add_argument("--commit", required=True, help="Commit esatto del main fidato, 40 caratteri.")
    parser.add_argument("--root", type=Path, default=Path("/srv/cora-tools/updater"))
    args = parser.parse_args()
    run(args.root, args.commit.strip().lower())


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        raise SystemExit("Operazione interrotta: " + str(error)) from None
