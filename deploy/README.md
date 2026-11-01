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
senza avviare una generazione. Il controllo usa lo stesso trasporto senza proxy del backend, anche se il container ha variabili HTTP_PROXY/HTTPS_PROXY:

```sh
docker compose --env-file deploy.env exec api python -c \
  'from core.ollama_transport import get_ollama_base_url,urlopen; print(urlopen(get_ollama_base_url()+"/api/tags",timeout=5).status)'
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
prima di modificarlo. Il workflow CI prevede verifiche per entrambi i target, un ciclo di build, avvio,
login, streaming e backup/ripristino su un'installazione sacrificabile. Il target
audio prepara un modello tiny di prova e verifica un'inferenza CPU offline su
silenzio sintetico; non misura la qualità su parlato reale. Il collaudo sul server
reale resta da eseguire, senza installazione automatica.

### Aggiornamento richiesto dall’interfaccia

Il servizio host separato in [updater/README.md](../updater/README.md) completa commit, build, backup, prova delle migrazioni su copia, applicazione e recupero da Programma. La prima installazione è manuale. Il normale `manage.py up` resta disponibile per il bootstrap e la manutenzione host; quando si usa l’updater, le immagini attive vengono gestite dal suo file di override privato: non eseguire in parallelo `manage.py up`, checkout o restore manuali.


### Override e impostazioni persistenti

Il Compose base imposta la modalità server e salva il modello selezionato in
`/state/runtime-settings.json`. L’assegnazione persistente per agente prevale sulla selezione globale; questa prevale sulle variabili modello per ruolo;
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

### Identità client del proxy

Nginx sovrascrive `X-Forwarded-For` con l'indirizzo della connessione ricevuta.
L'API usa quell'indirizzo per i tentativi di login solo se il peer appartiene a
`CORA_TRUSTED_PROXY_HOSTS` (nel Compose: servizio `web`, risolto via DNS Docker).
Non accetta catene di indirizzi o wildcard; Uvicorn non riscrive il peer dagli
header. Ricostruire API **e** web per applicare questa configurazione. Non
pubblicare direttamente la porta API. Se si aggiunge un ulteriore reverse proxy
prima di Nginx, il suo indirizzo sarà condiviso dai client finché non si configura
e verifica esplicitamente la catena fidata; non fidarsi di header Internet.

## Accesso automatico del proprietario tramite Tailscale Serve

Opzionale, solo sul server: il launcher Windows usa la modalità desktop locale; l’avvio manuale può usare password.
L’account proprietario deve essere già presente nel database. Dopo aver aggiornato
il checkout, eseguire sul server (sostituire email e origine con quelle reali):

```sh
python3 deploy/tailscale_login.py --login owner@example.com --origin https://server.tailnet.ts.net
```

Lo script controlla Serve, rifiuta Funnel e porte web pubblicate fuori da localhost,
ricava l’IP esatto del gateway Docker e mantiene tutti i file Compose del deployment
attivo. Salva un backup privato di `deploy.env`, configura l’identità autorizzata e
un segreto casuale fra proxy e API, quindi stampa il comando per ricostruire e
riavviare API e web. Eseguire quel comando, che conserva gli override/NAS esistenti.
Email e segreto restano in `deploy.env`, mai nel repository.

Dal telefono: attivare Tailscale con l’account configurato e aprire l’URL HTTPS
privato. Cora entra direttamente, senza cookie di sette giorni. Un altro account,
un’identità assente, un cookie precedente o header contraffatti inviati direttamente
all’API non danno accesso. Le scritture mantengono i controlli Origin e X-Cora-Client.
In Impostazioni viene spiegato che la disconnessione/revoca si gestisce in Tailscale.

Verificare `/backend/auth/status` dal browser del telefono: `authenticated: true`
e `mode: tailscale`. Dal server, `curl http://127.0.0.1:8090/backend/auth/status`
senza identità deve restituire `authenticated: false`. Un account non autorizzato
non deve poter leggere `/backend/conversations` né eseguire scritture.

Il proxy Nginx accetta l’identità Serve solo dall’IP host/gateway configurato e
sovrascrive sempre gli header interni. L’API richiede anche il segreto privato.
Questo si basa sulla fiducia nel server host: processi compromessi sul server
possono impersonare il proxy. Non pubblicare il web su LAN/Internet né l’API
sull’host; non attivare Funnel. Se cambia la rete Docker, rieseguire lo script:
un gateway diverso viene respinto, non autorizzato automaticamente.

Per tornare al login precedente, ripristinare il backup `deploy.env.before-tailscale-*`
su `deploy.env` e rieseguire il comando Compose stampato. La password proprietario
non viene modificata; può essere reimpostata con `python -m core.auth` nel container API.

## Modifiche rapide dal browser: Progetto Cora

La pagina File offre **Modifica testo** nelle risorse scrivibili: UTF-8 fino a
1 MiB, salvataggio esplicito, backup completo prima di sostituire il file,
controllo della revisione per evitare di sovrascrivere modifiche intervenute
dopo l'apertura. I backup `cora-backup-UUID.bak` sono nella cartella del file,
visibili e scaricabili dal browser; conservare il percorso indicato al salvataggio
per associarli al file originale. Non vengono eliminati automaticamente.
I file binari, i link e i file con collegamenti fisici non sono modificabili
con questo editor. Restano necessari i permessi Debian sulle cartelle/file.
L'editor è riservato al proprietario; non aggiunge strumenti agli agenti.

Per il server personale, dal checkout `/srv/cora-server-test`, **dopo aver
installato questa versione**:

```sh
docker compose --env-file deploy.env -f compose.yml -f compose.server-test.yml -f compose.files.yml -f compose.project-files.yml config --quiet
docker compose --env-file deploy.env -f compose.yml -f compose.server-test.yml -f compose.files.yml -f compose.project-files.yml up -d --build --wait api web
```

Omettere `-f compose.files.yml` se non esiste. L'override `compose.project-files.yml`
va sempre per ultimo: aggiunge il progetto host corrente in `/project` scrivibile,
conserva `/host` in sola lettura e le risorse NAS e Dati Cora. Un percorso alternativo
si imposta con `CORA_PROJECT_ROOT` in deploy.env. Non abilitarlo su installazioni
che non devono esporre il checkout. Non serve cambiare utente Docker o applicare
chmod ricorsivi. La Libreria IA continua a usare copie indipendenti.

Se è già installato l'updater host, il pulsante Aggiorna riusa il suo snapshot
Compose e occorre aggiungere il mount anche lì. Questo comando modifica soltanto
la risorsa `project` e il mount `/project`, preservando le altre impostazioni e
salvando un backup privato di compose.json. Eseguirlo con l'utente proprietario
dell'updater, **senza job di aggiornamento in corso**, con servizio fermo:

```sh
sudo systemctl stop cora-updater
python3 -m deploy.project_files --updater-root /srv/cora-updater --project-root /srv/cora-server-test
sudo systemctl start cora-updater
```

La configurazione diventa effettiva nei container al prossimo aggiornamento o
alla ricreazione manuale con gli override precedenti. Se si installa l'updater
per la prima volta, passare direttamente `--compose-file compose.project-files.yml`
per ultimo a `updater.setup`, insieme agli override esistenti.

L'editor modifica il **checkout sul server**, mentre Docker esegue codice già
incluso nelle immagini. Per eseguire una modifica locale ricostruire API/web con
il comando Compose precedente. Il pulsante di aggiornamento da GitHub costruisce
invece dal commit selezionato: non incorpora modifiche locali non committate.
Salvare e pubblicare le modifiche in Git prima di aggiornare da GitHub.
Per modifiche estese usare VS Code Remote - SSH, aprendo la stessa cartella
`/srv/cora-server-test` dopo la connessione SSH al server.

## Evidenze e servizi opzionali — audit 25 ottobre 2026

Questa è una procedura d’installazione, non l’inventario di un server attivo. `compose.yml` contiene PostgreSQL, API e web; non installa automaticamente Immich, Nextcloud, Ollama, worker desktop, terminale o Magazzino Tele. `deploy.env.example` usato da init imposta porta 8090; il fallback Compose senza quel valore è 8080. Gli override locali possono cambiare porte e mount: verificare la configurazione risolta prima dell’uso.

Il [worker](../worker/UPDATE.md) appartiene a un deployment distinto. Il [terminale personale](../docs/personal-terminal.md) richiede l’override `compose.terminal.yml`, configurazione Tailscale e host SSH espliciti. Per [app esterne](../docs/MANAGED_APPS.md), aggiornamenti e backup cifrati periodici opzionali vedere il [README updater](../updater/README.md). Il backup ordinario manage.py non equivale al backup cifrato updater: conserva deploy.env privato e non deve essere pubblicato.

Google Calendar ha token separato da Gmail: configurare `CORA_GOOGLE_CALENDAR_CREDENTIALS_PATH` e `CORA_GOOGLE_CALENDAR_TOKEN_PATH` secondo i percorsi nel container. `python3 deploy/manage.py google-calendar-auth` usa il helper OAuth con listener loopback e tunnel SSH dal computer; nessun token viene creato dalla sola build. Richiede interazione con il vero account e verifica dedicata.

`deploy/ci_verify.py` è esclusivamente una fixture sacrificabile: ferma servizi ed elimina volumi/state del proprio ambiente. Non eseguirla su un server con dati. Prevede build, login, evento SSE persistito, restore, inferenza audio su silenzio per il target CPU e prova updater; non prova la qualità di una chat reale o di una trascrizione. Nessuna di queste procedure è stata eseguita sul Debian reale durante questo audit. [Inventario, prove e residui](../docs/README_AUDIT_20261025.md).


## Google Calendar: rinnovo e ricollegamento dal sito

Il token di accesso si rinnova già automaticamente tramite refresh token. Un consenso revocato/scaduto richiede l'intervento del proprietario: Cora mostra "Autorizzazione Google da rinnovare" e il pulsante **Ricollega Google**. Il pulsante non si apre da solo e non viene avviato un loop di autorizzazioni. Un errore di rete temporaneo non richiede di cambiare account.

Per usare il pulsante serve una configurazione una tantum su Google Cloud. Il vecchio client Desktop usato dal comando SSH non può tornare all'indirizzo HTTPS del server.

1. Nel progetto Google Cloud già usato, aprire **Google Auth Platform → Client → Crea client → Applicazione web**. Non eliminare o modificare il client Gmail/Desktop esistente.
2. In **URI di reindirizzamento autorizzati** registrare l'indirizzo HTTPS del sito Cora seguito da `/google-calendar-callback.html`. Usare esattamente lo stesso dominio e porta aperti nel browser. Per esempio, se Cora è su `https://server.example`, registrare `https://server.example/google-calendar-callback.html`. Non usare `/backend` e non usare l'indirizzo di Nextcloud. Restano applicabili i requisiti Google sul dominio e sulla configurazione dell'app OAuth.
3. Scaricare il JSON di questo client web e salvarlo, con permessi privati e leggibile dall'utente del container API, nella cartella persistente del server: `state/google-calendar/web-credentials.json` (nel container `/state/google-calendar/web-credentials.json`). **Mai commettere questo file in Git**. Non sostituire `state/gmail/credentials.json`.
4. Nel `deploy.env` in uso aggiungere `CORA_GOOGLE_CALENDAR_WEB_CREDENTIALS_PATH=/state/google-calendar/web-credentials.json` e `CORA_GOOGLE_CALENDAR_WEB_REDIRECT_URI=` seguito dall'URL esatto del punto 2. `compose.yml` inoltra queste variabili mediante `env_file: deploy.env`. Ricreare il servizio API con gli stessi override Compose in uso; aggiornare anche il frontend per avere la pagina di ritorno statica.
5. Aprire Cora usando quell'origine HTTPS, andare in Calendario e premere **Ricollega Google**. Il consenso si apre nella stessa scheda e torna a una pagina con **Torna al Calendario**. Non servono tunnel SSH o porte aggiuntive. Nessun token o segreto viene mostrato nell'interfaccia. Se il consenso è annullato o la verifica fallisce, il token precedente resta intatto.

Il ritorno è una pagina statica pubblica, non un'API pubblica: il completamento usa il consueto POST autenticato, con protezione CSRF, PKCE, state e segreto per la singola scheda. Le sessioni scadono dopo dieci minuti e si possono consumare una sola volta. Il codice ricevuto viene rimosso dalla barra indirizzi prima della richiesta; Nginx non registra né memorizza in cache l'URL della pagina di ritorno. I token sono salvati atomicamente con permessi `0600`, soltanto dopo verifica del calendario con le nuove credenziali. Il cambio di identità OAuth continua a invalidare le vecchie approvazioni, tramite il fingerprint già presente.

**Scadenza ogni sette giorni:** verificare **Google Auth Platform → Pubblico → Stato di pubblicazione**. Con utente esterno e stato **Testing**, Google limita il refresh token Calendar a sette giorni. Per un uso continuativo valutare **In produzione** nella console del proprio progetto, rispettando gli eventuali requisiti richiesti da Google, poi ricollegare una volta l'account. Non rende pubblico il sito Cora, non dà accesso ai file e non richiede aprire porte del server. Non garantisce che un token non possa essere revocato o invalidato per altri motivi.

Il collegamento dal sito necessita di collaudo nel deploy reale con il client Google dell'utente; i test automatici simulano lo scambio e la verifica Google senza usare credenziali reali.
