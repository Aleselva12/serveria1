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

Aprire `http://localhost:8090`. `owner` chiede le credenziali sul terminale e
non modifica un proprietario già configurato. Non mettere password applicative
nei file versionati. `deploy.env` contiene invece una password PostgreSQL casuale,
è privato e non viene incluso nella build. Non sostituire quella password dopo
la creazione del volume PostgreSQL senza aggiornare anche il ruolo nel DB.

Il bind predefinito è localhost: per accesso remoto usare un reverse proxy
HTTPS/Tailscale verso `127.0.0.1:8090`, impostare `CORA_UI_ORIGINS` all'URL reale
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

L'immagine iniziale contiene le dipendenze core. Il profilo audio CPU descritto
sotto aggiunge Faster-Whisper; pyannote e la diarizzazione restano separati.
La chat e i tool documenti/calendario/mail sono presenti. Il collegamento Gmail
richiede credenziali e token già autorizzati in `state/gmail`; la configurazione
OAuth interattiva via browser non viene eseguita nel container headless.

## Audio CPU, modello locale

Impostare in `deploy.env`:

```dotenv
CORA_API_BUILD_TARGET=api-audio-cpu
CORA_WHISPER_CPU_THREADS=4
```

Poi costruire l'immagine e preparare il modello:

```sh
docker compose --env-file deploy.env build api
python3 deploy/manage.py audio-model small
python3 deploy/manage.py audio-check
python3 deploy/manage.py up
```

`audio-model` è l'unico passaggio online di preparazione: scarica i pesi pubblici
da Hugging Face senza token, non riceve audio e non avvia il servizio. Risolve
una revisione immutabile e registra revision/ID e checksum in
`state/models/whisper/cora-model.json`. Si può fissare la revisione con
`audio-model small --revision SHA_COMPLETO`. Rifiuta un modello già presente;
non mescola un download parziale con i pesi installati. Per importare un modello
già preparato copiare l'intera directory, incluso il manifest, mantenendo i
permessi dell'utente del container.

La trascrizione usa `/state/models/whisper`, CPU/int8, un worker e il numero di
thread configurato. `HF_HUB_OFFLINE=1` e `local_files_only=True` impediscono
download durante i tool; un modello mancante/incompleto viene segnalato.
`audio-check` verifica checksum e caricamento reale del motore senza trascrivere
file personali. Il modello è incluso nel backup di `state`; i modelli Ollama
restano esterni. I file da trascrivere vanno in `state/audio` (oppure in un bind
audio autorizzato), non automaticamente nella Libreria IA.

La cancellazione viene osservata prima/dopo il caricamento e fra i segmenti;
una fase nativa di decodifica già partita può terminare prima dell'arresto.
Non vengono inventati speaker: una richiesta di diarizzazione senza un motore
configurato continua a dichiararne l'indisponibilità.

## Collaudo della macchina reale

Sul PC Windows si può mantenere l'avvio nativo, senza migrare il database al
nuovo Compose. Chiudere Cora e usare `AVVIO.cmd -ConAudio` per installare la sola
trascrizione (la diarizzazione ha l'opzione distinta `-ConDiarizzazione`). Per
preparare lo stesso modello offline da PowerShell, nella radice della repository:

```powershell
.\.venv\Scripts\python.exe -m audio_agent.model_setup --model small --destination .\models\whisper
```

Impostare poi in `.env` `CORA_WHISPER_MODEL=./models/whisper`,
`CORA_WHISPER_LOCAL_ONLY=true`, `CORA_WHISPER_DEVICE=cpu`,
`CORA_WHISPER_COMPUTE_TYPE=int8` e `HF_HUB_OFFLINE=1`. Verificare:

```powershell
.\.venv\Scripts\python.exe -m audio_agent.model_setup --check
.\.venv\Scripts\python.exe -m deploy.doctor
```

`models/` è esclusa da Git. Il backup Docker include i modelli sotto `state`,
ma non la cartella del percorso nativo: copiarla separatamente insieme alla
configurazione quando si trasferisce il PC al server. Il lock Docker resta
specifico per Linux/Python 3.12; il launcher nativo usa i requirements CPU,
incluso il limite PyAV compatibile con Faster-Whisper.

```sh
python3 deploy/manage.py doctor
```

Il comando interroga PostgreSQL e la lista dei modelli Ollama, verifica cartelle
e permessi e, con il profilo audio, il manifest locale. Restituisce JSON con
`ok` e codice di uscita 0/1; non stampa credenziali, non genera testo, non carica
audio sul modello e non usa endpoint cloud. Non certifica la qualità della
trascrizione, il throughput o la disponibilità futura dei dischi.

Dopo esito positivo: verificare login, una chat breve, un file di prova nel File
Server e una breve registrazione audio propria. Controllare Attività e provare
il riavvio per confermare la persistenza. Il risultato di CI non equivale al
collaudo del proprio server e dei mount NAS.

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
prima di modificarlo. La CI verifica entrambi i target, un ciclo di build, avvio,
login, streaming e backup/ripristino su un'installazione sacrificabile. Il target
audio prepara un modello tiny di prova e verifica un'inferenza CPU offline su
silenzio sintetico; non misura la qualità su parlato reale. Il collaudo sul server
reale resta da eseguire, senza installazione automatica.

### Aggiornamento richiesto dall’interfaccia

Il servizio host separato in [updater/README.md](../updater/README.md) completa commit, build, backup, prova delle migrazioni su copia, applicazione e recupero da Programma. La prima installazione è manuale. Il normale `manage.py up` resta disponibile per il bootstrap e la manutenzione host; quando si usa l’updater, le immagini attive vengono gestite dal suo file di override privato: non eseguire in parallelo `manage.py up`, checkout o restore manuali.


### Override e impostazioni persistenti

Il Compose base imposta la modalità server e salva il modello selezionato in
`/state/runtime-settings.json`. La selezione globale prevale sui modelli per ruolo;
ogni nuova chiamata LLM, anche di un agente già caricato, usa la selezione corrente.
Una chiamata già in corso termina con il modello precedente.

Il Compose base espone soltanto i dati Cora. Per il NAS usare l'override che monta
la directory reale. Passare gli stessi override, nello stesso ordine, a ogni
operazione (anche backup, restore, doctor, owner e riavvio):

```bash
python3 deploy/manage.py check --compose-file compose.server-test.yml
python3 deploy/manage.py up --compose-file compose.server-test.yml
python3 deploy/manage.py backup /percorso/privato/snapshot --compose-file compose.server-test.yml
```

`--compose-file` è ripetibile; i percorsi relativi sono riferiti alla radice del
repository. Il backup non include i dati NAS esterni né i file override:
conservarne una copia e ripassarli sul nuovo host al ripristino.

Installazioni già inizializzate: non ripetere `init` e non sovrascrivere
`deploy.env`. Verificare `CORA_FILE_ROOTS`: `/nas/drive` richiede il relativo
mount. Prima di ricreare un vecchio container, salvare l'eventuale selezione in
`/app/data/runtime-settings.json` oppure riselezionare il modello dalla UI dopo
l'aggiornamento. Il nuovo percorso persistente è incluso nel backup di `/state`.
