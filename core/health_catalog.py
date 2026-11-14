"""Canonical registry of health checks and cross-component boundaries.

A check is registered ONCE here. Its id is reused by the periodic runner, DB
history, Home, Machines and managed applications. Manual checks are proposals,
never silently executed against real data.
"""
from __future__ import annotations


def entry(id, title, component, kind, stage, frequency, *, depends=(), description=""):
    return {"id": id, "title": title, "component": component, "kind": kind,
            "stage": stage, "frequency": frequency, "dependsOn": list(depends),
            "description": description, "automated": frequency == "5m",
            "maxAgeSeconds": 600 if frequency == "5m" else 86400,
            # Run once per installed release: valid until the commit changes, not for 24h only.
            "releaseScoped": frequency in ("on_release", "on_change")}

_CATALOG = [
    entry("database", "PostgreSQL leggibile", "cora", "preflight", "API → DB", "5m"),
    entry("library", "Libreria IA leggibile", "files", "preflight", "API → Libreria", "5m"),
    entry("audio", "Motore trascrizione disponibile", "audio", "preflight", "Audio → Whisper", "5m"),
    entry("ollama", "Catalogo modelli Ollama", "worker", "preflight", "API → Ollama", "5m"),
    entry("word_sample", "Word: aggiunta su documento sintetico", "audio", "synthetic", "Word → parser → append", "5m"),
    entry("chat_contract", "Chat → orchestratore → agenti (contratti)", "cora", "contract", "Chat API → grafo → delega", "5m",
          depends=("database",), description="Rileva route, nodi e tool di delega scollegati senza inferenza."),
    entry("orchestrator_v1_contract", "Orchestratore V1: coordinamento interno (contratti)", "cora", "contract", "A/B → registry → coordinator → bus → context/error policy", "5m",
          description="Verifica strutturale non distruttiva della base W1 senza inferenza, scheduling o effetti esterni."),
    entry("audio_word_contract", "Audio → analisi → approvazione Word (contratti)", "audio", "contract", "Audio API → proposta → Word", "5m",
          depends=("audio", "library"), description="Controlla endpoint e funzioni, non scrive documenti."),
    entry("calendar_contract", "Calendario → approvazioni → Google (contratti)", "calendar", "contract", "Calendar API → strumenti", "5m",
          depends=("database",), description="Controlla i collegamenti del codice, non crea eventi."),
    entry("worker_contract", "Orchestratore → worker (contratti)", "worker", "contract", "Modello → macchina → worker", "5m",
          depends=("ollama",), description="Controlla route e risolutori senza accendere modelli."),
    # Gmail checks below use contract inspection and simulated transport only.
    entry("gmail_contract", "Gmail: contratti lettura e bozze", "gmail", "contract",
          "Gmail → strumenti → approvazioni", "on_release",
          description="Contratti di codice; non accede agli account."),
    entry("gmail_e2e", "Gmail: bozza MIME con trasporto simulato", "gmail", "synthetic",
          "Gmail → bozza MIME → trasporto simulato", "on_release",
          depends=("gmail_contract",),
          description="Bozza sintetica; account Google, autorizzazioni e invio reali esclusi."),
    entry("chat_e2e", "Chat: grafo, deleghe e strumenti isolati", "cora", "synthetic", "Chat → grafo → agente simulato", "on_release",
          depends=("chat_contract", "database"), description="Grafo compilato con agente simulato; modello e persistenza reali esclusi."),
    entry("memory_e2e", "Memoria riletta da un nuovo processo", "cora", "e2e", "Memoria → PostgreSQL → lettura", "on_release"),
    entry("audio_e2e", "Audio e Word: regressioni isolate", "audio", "synthetic", "Configurazione audio → Word sintetico", "on_release",
          depends=("audio_word_contract",), description="Configurazione, parser e trasformazioni su campioni; trascrizione e LLM reali esclusi."),
    entry("calendar_e2e", "Google Calendar: scrittura confermata con rilettura", "calendar", "e2e", "Provider Calendar → OAuth test → Google", "on_release",
          depends=("calendar_contract",), description="Provider reale: scrittura confermata con rilettura durante uso normale o account test. Duplicati e approvazioni hanno regressioni separate."),
    entry("files_e2e", "File: upload/download HTTP su campione temporaneo", "files", "synthetic", "API → cartella temporanea → integrità", "on_release"),
    entry("immich_e2e", "Immich: raggiungibilità HTTP", "immich", "preflight", "API → endpoint configurato; upload escluso", "daily"),
    entry("nextcloud_e2e", "Nextcloud: raggiungibilità HTTP", "nextcloud", "preflight", "API → endpoint configurato; file reali esclusi", "daily"),
    entry("magazzino_e2e", "Magazzino: installazione e allowlist isolate", "magazzino_tele", "synthetic", "Manager applicazioni simulato; import escluso", "on_release"),
    entry("preventivi_e2e", "Preventivi: generazione e rilettura PDF sintetico", "preventivi", "synthetic", "Dati → generatore → PDF", "on_release"),
    entry("dependency_audit", "Dipendenze Python: vulnerabilità note (OSV)", "cora", "preflight",
          "API → pacchetti installati → database OSV", "on_release",
          description="Confronta nomi e versioni dei pacchetti installati nell'API con il database pubblico OSV; nessun altro dato inviato. Gravi: errore; medie/basse: avviso."),
    entry("worker_e2e", "Chat agente su worker e modello effettivo", "worker", "e2e", "Agente → worker assegnato → /chat", "on_change",
          depends=("worker_contract",)),
    entry("debian_host_e2e", "Debian host: identità, permessi e stato pacchetti", "cora", "e2e",
          "API → updater host → Debian", "on_change",
          description="Host reale in sola lettura: Debian, UID/GID updater, file privati, dpkg audit e simulazione APT; non installa aggiornamenti."),
    entry("systemd_host_e2e", "systemd host: updater attivo e unità coerente", "cora", "e2e",
          "API → updater host → systemd", "on_change",
          description="Interroga solo cora-updater.service; nessun restart/stop/start e nessun contenuto del journal."),
    entry("host_admin_e2e", "Amministrazione host: SSH e configurazione servizi", "cora", "e2e",
          "API → updater host → ssh.service", "on_change",
          description="Verifica caricamento/stato di ssh.service e presenza delle unità; non apre connessioni SSH e non legge credenziali."),
    entry("desktop_e2e", "Desktop: inferenza e modello effettivo", "worker", "e2e", "API → desktop configurato → modello", "on_change"),
    entry("laptop_e2e", "Laptop: inferenza e modello effettivo", "worker", "e2e", "API → laptop configurato → modello", "on_change"),
    entry("memory_regression", "Memoria e contratti contesto: regressioni", "cora", "synthetic", "Test isolati → contesto", "on_release"),
    entry("calendar_regression", "Calendario e approvazioni: regressioni", "calendar", "synthetic", "Test isolati → approvazioni", "on_release"),
    entry("orchestration_regression", "Orchestrazione: regressioni", "cora", "synthetic", "Test isolati → coordinamento ed errori", "on_release"),
    entry("files_regression", "File: regressioni", "files", "synthetic", "Test isolati → scrittura e modifica", "on_release"),
    entry("backup_restore", "Backup: integrità e protezioni isolate", "backups", "synthetic", "Fixture archivio → controlli restore; DB reale escluso", "periodic_isolated"),
    entry("updates_rollback", "Updater: rollback e recupero isolati", "backups", "synthetic", "Updater simulato → recupero; rilascio reale escluso", "on_release"),
]

_CATALOG.append(entry('files_browse_regression', 'File: elenco, filtri e paginazione', 'files', "synthetic", "Fixture isolate → funzioni e API", "on_release", description="Regressioni su dati temporanei; installazione, browser e dati reali esclusi."))
_CATALOG.append(entry('files_lifecycle_regression', 'File: copia, spostamento, cestino e ripristino', 'files', "synthetic", "Fixture isolate → funzioni e API", "on_release", description="Regressioni su dati temporanei; installazione, browser e dati reali esclusi."))
_CATALOG.append(entry('files_access_regression', 'File: accesso, sola lettura e confinamento', 'files', "synthetic", "Fixture isolate → funzioni e API", "on_release", description="Regressioni su dati temporanei; installazione, browser e dati reali esclusi."))
_CATALOG.append(entry('word_document_regression', 'Word: lettura, modifica protetta, backup e conflitti', 'audio', "synthetic", "Fixture isolate → funzioni e API", "on_release", description="Regressioni su dati temporanei; installazione, browser e dati reali esclusi."))

from core.verify.tree_verification_suites import SUITES as TREE_SUITES

_CATALOG.extend(entry(key, item["title"], item["component"], "synthetic", "Suite isolate su fixture", "on_release", description=item["scope"]) for key, item in TREE_SUITES.items())

CATALOG = {item["id"]: item for item in _CATALOG}
assert len(CATALOG) == len(_CATALOG), "ID di controlli duplicati"
COMPONENTS = {
    "cora": "Cora e memoria",
    "files": "File e Libreria IA",
    "audio": "Audio e Word",
    "calendar": "Calendario",
    "gmail": "Email e Gmail",
    "worker": "Worker e modelli",
    "immich": "Immich",
    "nextcloud": "Nextcloud",
    "magazzino_tele": "Magazzino Tele",
    "preventivi": "Preventivi",
    "backups": "Backup e aggiornamenti",
}
