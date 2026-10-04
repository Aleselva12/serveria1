# Installazione Debian: Docker Compose e Ollama esterno

Questo è il percorso di installazione del backend FastAPI, del frontend compilato
e di PostgreSQL + pgvector. Non sostituisce Immich, Nextcloud o altri servizi.
Ollama e i suoi modelli restano esterni; non vengono scaricati automaticamente.
Richiede Docker Engine con Compose v2, Git e Python 3 sul server Debian.

## Primo avvio

Dal checkout della versione da installare:

```sh
python3 deploy/manage.py init
# Modificare deploy.env: URL Ollama, modelli e origine browser effettiva.
python3 deploy/manage.py check
python3 deploy/manage.py up
python3 deploy/manage.py owner
```

Aprire `http://localhost:8080`. `owner` chiede le credenziali sul terminale e
non modifica un proprietario già configurato. Non mettere password applicative
nei file versionati. `deploy.env` contiene invece una password PostgreSQL casuale,
è privato e non viene incluso nella build. Non sostituire quella password dopo
la creazione del volume PostgreSQL senza aggiornare anche il ruolo nel DB.

Il bind predefinito è localhost: per accesso remoto usare un reverse proxy
HTTPS/Tailscale verso `127.0.0.1:8080`, impostare `CORA_UI_ORIGINS` all'URL reale
e `CORA_COOKIE_SECURE=true` con HTTPS. UI e API condividono la stessa origine.
PostgreSQL e l'API non pubblicano porte sull'host; `/backend` passa dal proxy
Nginx, che disabilita il buffering SSE. Un solo worker esegue il runtime.

`host.docker.internal` raggiunge l'host Docker, non il PC da cui si apre il
browser. Se Ollama è su un'altra macchina usare il suo indirizzo privato.
Se è sullo stesso host deve ascoltare su un indirizzo raggiungibile dalla rete
Docker; un listener limitato a `127.0.0.1` non basta. Verificare la raggiungibilità
senza avviare una generazione:

```sh
docker compose --env-file deploy.env exec api python -c \
  'import os,urllib.request; print(urllib.request.urlopen(os.environ["OLLAMA_BASE_URL"].rstrip("/")+"/api/tags",timeout=5).status)'
```

L'immagine iniziale contiene le dipendenze core, non Faster-Whisper e
pyannote. La chat e i tool documenti/calendario/mail sono presenti; trascrizione
e diarizzazione richiedono il successivo profilo audio. Il collegamento Gmail
richiede credenziali e token già autorizzati in `state/gmail`; la configurazione
OAuth interattiva via browser non viene eseguita nel container headless.

## Persistenza e mount

- PostgreSQL usa il volume Compose `postgres_data`.
- `state/` contiene file Cora, libreria IA e originali separati, audio,
  trascrizioni, preventivi, bozze e credenziali Gmail.
- Il codice resta nell'immagine e non è scrivibile dall'utente Cora.
- `init` genera UID/GID coerenti con l'utente host (1000 se eseguito da root).
  Cambiarli richiede ricostruire l'immagine e preparare i permessi dei dati.

Per collegare il NAS aggiungere un bind mount esplicito in un override Compose
locale e una voce `CORA_FILE_ROOTS` con il **percorso nel container**. Usare
`create_host_path: false` per segnalare un disco assente invece di creare una
cartella vuota. Non montare `/` o gli archivi interni di altri servizi come
cartelle scrivibili. Libreria IA e originali rimangono cartelle distinte.
Il backup seguente comprende `state` e il DB, non mount NAS aggiunti separatamente
né i modelli Ollama. Questi hanno una propria politica di backup.

## Backup e ripristino verificabile

```sh
python3 deploy/manage.py backup /percorso/privato/cora-2026-10-04
python3 deploy/manage.py verify-backup /percorso/privato/cora-2026-10-04
```

Il backup ferma API e web, attende l'arresto del runtime, produce un dump
PostgreSQL custom e un archivio di `state`, conserva `deploy.env`, commit,
identità delle immagini e checksum. Dopo successo riavvia Cora. Se fallisce
lascia l'app ferma e non produce un manifest valido. Serve spazio per una copia
completa; proteggere il backup come i dati originali. `verify-backup` controlla
integrità, non sostituisce una prova reale di ripristino.

Per ripristinare su **un target nuovo**: fare checkout del commit registrato nel
manifest, eseguire `init`, adattare `deploy.env`, costruire le immagini e avviare
solo PostgreSQL, quindi:

```sh
docker compose --env-file deploy.env build
python3 deploy/manage.py restore /percorso/privato/cora-2026-10-04
python3 deploy/manage.py up
```

Il ripristino rifiuta un database con tabelle o `state` contenente file/link;
non cancella dati esistenti. Usa la password DB del nuovo target, non copia
automaticamente il vecchio `deploy.env`, revoca le sessioni e lascia l'app ferma
fino al controllo della configurazione. L'avvio successivo recupera run interrotti
e operazioni incerte senza rieseguire effetti. Non copiare a caldo il volume DB.

## Aggiornamento e rollback

1. Creare e verificare un backup della versione attuale.
2. Fare checkout del commit/release approvato; impostare `CORA_RELEASE` a quel
   commit per conservare tag immagine distinguibili.
3. Eseguire `check`, poi `up`. Controllare login, `/runtime` e un turno reale.
4. In caso di migrazione incompatibile, ripristinare il backup su un target
   vuoto con la versione precedente. Non puntare codice vecchio a un DB nuovo.

Le dipendenze Python sono fissate con hash in `requirements-deploy.lock` e il
frontend usa `npm ci` con `package-lock.json`. Le immagini di base hanno tag
di versione e possono ricevere patch: non è una garanzia di immagini identiche
bit per bit; salvare ID/digest e immagini per rollback offline. Per aggiornare
il lock in modo esplicito e rieseguire la CI:

```sh
uv pip compile requirements-core.txt --python-version 3.12 \
  --python-platform x86_64-unknown-linux-gnu --generate-hashes \
  --no-annotate --no-header -o requirements-deploy.lock
```

Lo schema è versionato con checksum; leggere `database/migrations/README.md`
prima di modificarlo. La CI verifica un ciclo di build, avvio, login, streaming
e backup/ripristino su un'installazione sacrificabile. Il collaudo sul server
reale e il profilo audio restano passi successivi, senza installazione automatica.
