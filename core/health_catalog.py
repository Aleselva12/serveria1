"""Canonical registry of health checks and cross-component boundaries.

A check is registered ONCE here. Its id is reused by the periodic runner, DB
history, Home, Machines and managed applications. Manual checks are proposals,
never silently executed against real data.
"""
from __future__ import annotations

def entry(id, title, component, kind, stage, frequency, *, depends=(), description=""):
    return {"id": id, "title": title, "component": component, "kind": kind,
            "stage": stage, "frequency": frequency, "dependsOn": list(depends),
            "description": description, "automated": frequency == "5m"}

_CATALOG = [
    entry("database", "PostgreSQL leggibile", "cora", "preflight", "API → DB", "5m"),
    entry("library", "Libreria IA leggibile", "files", "preflight", "API → Libreria", "5m"),
    entry("audio", "Motore trascrizione disponibile", "audio", "preflight", "Audio → Whisper", "5m"),
    entry("ollama", "Catalogo modelli Ollama", "worker", "preflight", "API → Ollama", "5m"),
    entry("word_sample", "Word: aggiunta su documento sintetico", "audio", "synthetic", "Word → parser → append", "5m"),
    entry("chat_contract", "Chat → orchestratore → agenti (contratti)", "cora", "contract", "Chat API → grafo → delega", "5m",
          depends=("database",), description="Rileva route, nodi e tool di delega scollegati senza inferenza."),
    entry("audio_word_contract", "Audio → analisi → approvazione Word (contratti)", "audio", "contract", "Audio API → proposta → Word", "5m",
          depends=("audio", "library"), description="Controlla endpoint e funzioni, non scrive documenti."),
    entry("calendar_contract", "Calendario → approvazioni → Google (contratti)", "calendar", "contract", "Calendar API → strumenti", "5m",
          depends=("database",), description="Controlla i collegamenti del codice, non crea eventi."),
    entry("worker_contract", "Orchestratore → worker (contratti)", "worker", "contract", "Modello → macchina → worker", "5m",
          depends=("ollama",), description="Controlla route e risolutori senza accendere modelli."),
    entry("chat_e2e", "Chat e agente: risposta e persistenza", "cora", "e2e", "Chat → modello → DB", "on_release",
          depends=("chat_contract", "database"), description="Necessario test isolato con modello controllato."),
    entry("memory_e2e", "Memoria dopo riavvio", "cora", "e2e", "Memoria → PostgreSQL → lettura", "on_release"),
    entry("audio_e2e", "Trascrizione campione e Word approvato", "audio", "e2e", "Audio → LLM → Word", "on_release",
          depends=("audio_word_contract",), description="Solo in ambiente isolato, mai sui Word utenti."),
    entry("calendar_e2e", "Google Calendar e duplicati", "calendar", "e2e", "Calendar → OAuth → Google", "on_release",
          depends=("calendar_contract",), description="Solo calendario test dedicato."),
    entry("files_e2e", "Upload, download e integrità", "files", "e2e", "Browser → Cora → NAS", "on_release"),
    entry("immich_e2e", "Immich: foto test e recupero", "immich", "e2e", "API → Immich → archivio", "daily"),
    entry("nextcloud_e2e", "Nextcloud: file test e recupero", "nextcloud", "e2e", "API → Nextcloud → archivio", "daily"),
    entry("magazzino_e2e", "Magazzino Tele: import Excel campione", "magazzino_tele", "e2e", "Import → ordini → database", "on_release"),
    entry("preventivi_e2e", "Preventivi: PDF campione", "preventivi", "e2e", "Dati → generatore → PDF", "on_release"),
    entry("worker_e2e", "Inferenza worker e modello effettivo", "worker", "e2e", "Cora → Tailscale → GPU", "on_change",
          depends=("worker_contract",)),
    entry("backup_restore", "Backup e ripristino su DB vuoto", "backups", "e2e", "Backup → restore → verifica", "periodic_isolated"),
    entry("updates_rollback", "Deploy e rollback controllato", "backups", "e2e", "Updater → container → DB", "on_release"),
]

CATALOG = {item["id"]: item for item in _CATALOG}
assert len(CATALOG) == len(_CATALOG), "ID di controlli duplicati"
COMPONENTS = {
    "cora": "Cora e memoria",
    "files": "File e Libreria IA",
    "audio": "Audio e Word",
    "calendar": "Calendario",
    "worker": "Worker e modelli",
    "immich": "Immich",
    "nextcloud": "Nextcloud",
    "magazzino_tele": "Magazzino Tele",
    "preventivi": "Preventivi",
    "backups": "Backup e aggiornamenti",
}
