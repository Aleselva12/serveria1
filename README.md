# Cora Lab

Cora Lab è l'attuale proof of concept locale di Cora: un assistente multi-agente eseguito sul PC Windows, con modello LLM locale tramite Ollama, orchestrazione LangGraph, backend FastAPI e interfaccia React/Vite.

Questo README descrive esclusivamente lo stato implementato nella repository.

## Architettura attuale

```text
React / Vite
      ↓
FastAPI
      ↓
Cora / Supervisor LangGraph
├── strumenti locali
├── Structure Agent
├── Local Research Agent
├── Audio Agent
└── Email & Quotes Agent
      ↓
Ollama locale
```

Il Supervisor è il punto centrale di ingresso. Riceve la richiesta dell'utente, può rispondere direttamente oppure delegare a uno strumento locale o a uno dei quattro agenti specializzati.

Tutti gli agenti LLM usano la configurazione Ollama definita nelle variabili d'ambiente. La configurazione predefinita è:

```env
OLLAMA_MODEL=gpt-oss:20b
OLLAMA_BASE_URL=http://localhost:11435
```

## Supervisor

Il Supervisor è definito principalmente in:

```text
graph.py
prompt.py
tools.py
```

Usa LangGraph e `MemorySaver` per mantenere lo stato della conversazione durante l'esecuzione. È inoltre presente una memoria persistente locale separata, basata su SQLite.

Il Supervisor può usare direttamente questi strumenti locali:

- calcolatrice per operazioni aritmetiche di base;
- lettura dello stato reale di CPU, RAM e disco;
- elenco dei file autorizzati della repository;
- lettura dei file testuali autorizzati della repository;
- lettura del registro centrale di struttura e capacità.

Può inoltre delegare ai quattro agenti specializzati.

## Registro centrale di struttura e capacità

Il progetto contiene ora un nucleo condiviso:

```text
core/
├── capabilities.py
└── registry.py
```

`capabilities.py` definisce lo schema comune usato per descrivere componenti e capacità.

`registry.py` è la fonte centrale per sapere quali componenti sono definiti nel sistema. Registra attualmente il Supervisor, i quattro agenti specializzati, i tool locali principali, il backend FastAPI e l'interfaccia React.

Per ogni componente sono descritti identificativo, nome, tipo, descrizione, capacità dichiarate, modulo associato e dipendenze strutturali.

Il registro può verificare se il modulo Python associato è disponibile e restituisce uno stato strutturale del componente. Questo controllo non sostituisce gli health check runtime dei servizi esterni.

Il Supervisor accede al registro tramite:

```text
structure_registry_tool
```

Il registro include il Permission Engine tra i componenti core. Logging e memoria persistente restano componenti separati e registrati.

## Ownership, piani e permessi

Il progetto contiene ora tre moduli core aggiuntivi:

```text
core/
├── orchestration.py
├── permissions.py
└── plans.py
```

### Ownership provvisoria

I piani e i task usano sempre:

```text
owner = orchestrator
```

L'orchestratore leggero ispirato a reti biologiche non è ancora implementato. `core/orchestration.py` mantiene quindi questa ownership attraverso un resolver deterministico di fallback.

Il fallback non esegue e non instrada autonomamente i task. Serve soltanto a mantenere stabile il contratto dei piani finché verrà collegato l'orchestratore reale.

Ogni task separa l'owner dal componente che dovrebbe eseguire materialmente il lavoro:

```text
owner: orchestrator
target_component: email_quotes_agent
```

### Artefatti strutturati

`core/plans.py` definisce e salva tre tipi di artefatti runtime:

```text
structure_workspace/
├── plans/
├── evaluations/
└── management/
```

I piani contengono obiettivo, owner, priorità, stato, task, dipendenze, azioni richieste, target component, output attesi, criteri di valutazione, rischi, blocker, checkpoint e criteri di completamento.

Le evaluation distinguono criteri, evidenze, elementi passed, failed e unknown, rischi, correzioni richieste e raccomandazione.

Gli artefatti management conservano priorità, dipendenze, handoff e prossimi passi.

Il workspace è escluso da Git ed è configurabile con:

```env
CORA_STRUCTURE_WORKSPACE=./structure_workspace
```

### Permission Engine

`core/permissions.py` implementa un controllo deterministico dei permessi per singola azione.

Livelli attualmente definiti:

```text
OBSERVE
READ
DRAFT
WRITE
EXECUTE
ADMIN
```

Ogni azione ha inoltre una policy:

```text
AUTO
CONFIRM
BLOCKED
```

`CONFIRM` può essere sbloccata da un'approvazione esplicita dell'utente. `BLOCKED` rimane vietata finché la configurazione della policy non viene modificata deliberatamente; un agente non può auto-elevarsi.

Le azioni oggi implementate di Supervisor, Structure Agent, Local Research Agent, Audio Agent ed Email & Quotes Agent sono coperte da regole esplicite e i rispettivi tool eseguono il controllo prima dell'azione. Lo Structure Agent resta limitato al proprio workspace e non può modificare codice sorgente, configurazione core, memoria persistente o eseguire azioni esterne. La sovrascrittura distruttiva di Word e l'invio email sono bloccati.

Le policy attuali sono intenzionalmente provvisorie: le operazioni locali già previste restano utilizzabili, mentre il flusso completo CONFIRM/approvals verrà raffinato insieme alle pagine che lo espongono. Lo smoke check verifica anche duplicati e copertura delle regole.

## Logging e memoria persistente

Il core contiene ora due componenti distinti ma collegati:

```text
core/
├── logging.py
└── memory.py
```

### Logging

`core/logging.py` scrive eventi strutturati append-only in formato JSONL.

Percorso predefinito:

```env
CORA_LOG_ROOT=./logs
```

File runtime:

```text
logs/cora.jsonl
```

Gli eventi includono identificativo, timestamp UTC, tipo evento, componente, stato, thread, durata e metadati tecnici. Il logging evita di salvare automaticamente il contenuto completo dei messaggi utente.

Sono già registrati almeno:

- richieste chat al Supervisor;
- deleghe agli agenti specializzati;
- letture della memoria;
- scritture della memoria;
- cancellazioni dalla memoria;
- errori nelle operazioni osservate.

Il Supervisor può leggere gli eventi recenti tramite `recent_system_events_tool`.

### Memoria persistente

`core/memory.py` usa SQLite locale e non richiede una nuova dipendenza Python esterna.

Percorso predefinito:

```env
CORA_MEMORY_ROOT=./data
CORA_MEMORY_DB=./data/cora_memory.sqlite3
```

La memoria è strutturata e supporta attualmente questi tipi:

```text
fact
preference
person
project
decision
note
task_context
```

Ogni memoria contiene almeno ID, tipo, chiave, contenuto, fonte, importanza, data di creazione, data di aggiornamento, eventuale scadenza e metadati.

Sono disponibili tre operazioni al Supervisor:

- `remember_tool`: crea o aggiorna una memoria;
- `recall_memory_tool`: ricerca nella memoria persistente;
- `forget_memory_tool`: elimina una memoria per ID.

La regola attuale è conservativa: Cora non salva automaticamente tutte le conversazioni e non trasforma automaticamente il log in memoria. Le scritture persistenti avvengono solo su richiesta esplicita o in un workflow esplicitamente autorizzato.

Ogni operazione sulla memoria genera a sua volta un evento nel log, creando il collegamento tra memoria e osservabilità senza confondere i due livelli.

## Structure Agent

Cartella:

```text
structure_agent/
```

Lo Structure Agent è l'agente di livello sistema dedicato a quattro responsabilità principali:

- **Planner**: trasforma obiettivi in passi ordinati, dipendenze, checkpoint e assegnazioni ai componenti adatti;
- **Evaluation**: valuta piani, output e implementazioni rispetto a obiettivi, criteri e vincoli espliciti;
- **Control**: controlla struttura dichiarata, stato runtime, memoria e log per individuare anomalie, mismatch e dipendenze mancanti;
- **Management**: mantiene una vista di priorità, avanzamento, handoff e prossimi passi tra componenti e agenti.

Per svolgere questi compiti può:

- interrogare il registro centrale di componenti e capacità;
- leggere lo stato reale di CPU, RAM e disco;
- leggere le statistiche tecniche della memoria persistente;
- analizzare gli eventi recenti del log strutturato;
- ottenere uno snapshot combinato di controllo del sistema;
- elencare e leggere i file testuali autorizzati del progetto;
- produrre piani, checklist, valutazioni, decisioni e istruzioni di handoff;
- salvare plan, evaluation e management artifact strutturati nel proprio workspace;
- consultare il manifest dei permessi e lo stato del resolver dell'owner.

La sua autorità di esecuzione è per ora volutamente limitata: può scrivere soltanto piani, evaluation e artefatti di management nel workspace dedicato. Non può modificare codice, configurazione core o memoria persistente e non esegue azioni esterne.

Il modello può essere configurato separatamente:

```env
CORA_MODEL_STRUCTURE=
```

Se la variabile è vuota, eredita `OLLAMA_MODEL`.

## Local Research Agent

Cartella:

```text
search_agent/
```

Lavora su documenti locali autorizzati e non effettua ricerche Internet.

Capacità implementate:

- elenco dei documenti disponibili;
- ricerca lessicale nei documenti;
- lettura del contenuto;
- analisi tramite il modello locale;
- supporto a file testuali comuni, documenti Word `.docx` e PDF testuali;
- creazione di nuovi Word e aggiornamento non distruttivo di Word esistenti tramite append;
- sovrascrittura distruttiva di Word bloccata dalla policy corrente;
- protezione dai percorsi esterni alla directory autorizzata;
- limiti configurabili per dimensione del file e quantità di testo passata al modello.

Directory predefinita:

```env
CORA_KNOWLEDGE_ROOT=./knowledge
```

## Audio Agent

Cartella:

```text
audio_agent/
```

Lavora su file audio locali autorizzati.

Capacità implementate:

- elenco dei file audio;
- trascrizione locale tramite `faster-whisper`;
- timestamp della trascrizione;
- supporto ai principali formati audio e ad alcuni contenitori video;
- diarizzazione opzionale tramite un modello locale `pyannote`;
- etichette generiche degli speaker come `Interlocutore 1`, `Interlocutore 2`, ecc.;
- riassunto o analisi della trascrizione tramite l'agente;
- salvataggio opzionale della trascrizione in un file `.txt`.

Configurazione principale:

```env
CORA_AUDIO_ROOT=./audio
CORA_TRANSCRIPT_ROOT=./audio/_transcripts
CORA_WHISPER_MODEL=small
CORA_WHISPER_DEVICE=cpu
CORA_WHISPER_COMPUTE_TYPE=int8
CORA_DIARIZATION_MODEL=
```

Se la diarizzazione non è configurata o fallisce, la trascrizione può comunque essere prodotta senza attribuzione degli speaker.

## Email & Quotes Agent

Cartella:

```text
email_agent/
```

Capacità implementate:

- ricerca nell'archivio Gmail tramite sintassi di ricerca Gmail;
- recupero delle email di una giornata;
- sintesi e analisi delle email recuperate tramite il modello locale;
- scrittura del testo di email;
- salvataggio di bozze Gmail solo quando richiesto esplicitamente;
- generazione locale di preventivi PDF da dati strutturati;
- calcolo di imponibile, IVA e totale del preventivo.

Configurazione principale:

```env
CORA_GMAIL_CREDENTIALS_PATH=./email_agent/credentials.json
CORA_GMAIL_TOKEN_PATH=./email_agent/token.json
CORA_EMAIL_MAX_BODY_CHARS=6000
CORA_QUOTE_ROOT=./quotes
```

Le credenziali Gmail e il token OAuth non sono versionati nella repository.

Il generatore di preventivi richiede attualmente dati già strutturati, compresi descrizione, quantità e prezzo unitario. Il codice non recupera automaticamente prezzi o condizioni commerciali da cataloghi esterni.

## Backend API

File:

```text
api.py
```

Il backend usa FastAPI.

Endpoint presenti:

```text
GET  /health
GET  /capabilities
POST /chat
```

`/health` restituisce lo stato del backend, la raggiungibilità di Ollama, il modello effettivo del supervisore (incluso CORA_MODEL_SUPERVISOR) e l'elenco degli agenti letto dal registro centrale.

`/capabilities` restituisce il registro centrale dei componenti e delle capacità.

`/chat` riceve il messaggio dell'utente e un eventuale `thread_id`, invoca il grafo principale e restituisce la risposta di Cora.

Il backend locale usa di default:

```text
http://127.0.0.1:8000
```

## File server — backend

La pagina File è destinata a due sottopagine: **File server** e **Libreria IA**. Il selettore sarà su una riga separata sotto il titolo File; entrambe useranno lo stesso stile. In questa fase è implementato soltanto il backend di File server: il frontend mantiene ancora gli avvisi e i controlli disabilitati.

`core/server_files.py` espone operazioni sul filesystem indipendenti da Ollama, dal grafo e dal knowledge root degli agenti. Un upload qui non rende automaticamente il documento disponibile all'IA.

Prefisso di tutti i percorsi: `/api/v1/server/files`.

| Metodo e percorso | Operazione / parametri |
| --- | --- |
| `GET /roots` | Risorse configurate, disponibilità e spazio del filesystem di ogni risorsa. |
| `GET /children` | `root_id`, `path` relativo (vuoto = radice), `query`, `offset`, `limit` (1–500). Cartelle prima dei file; filtro nomi nella cartella corrente. |
| `GET /download` | `root_id`, `path`; download di un file normale come allegato. |
| `POST /folders` | JSON `{root_id, path}`; crea una cartella con genitore esistente. |
| `POST /upload` | Multipart: `root_id`, `path` della cartella e `file`. Un file per richiesta; la futura UI può inviare più richieste. |
| `POST /transfer` | JSON `{root_id, path, destination, mode}`; copia (`copy`) o sposta/rinomina (`move`) nella stessa risorsa. |
| `POST /trash` | JSON `{root_id, path}`; spostamento nel cestino persistente della risorsa. |
| `GET /trash` | `root_id`; elenco elementi nel cestino. |
| `POST /restore` | JSON `{root_id, id}`; ripristina nel percorso originale senza sostituire file esistenti. |

Le risposte dell'elenco comprendono percorso relativo, nome, tipo, dimensione dei file, ultima modifica, MIME e capacità ammesse dalla policy. I permessi del sistema operativo restano vincolanti. I link sono mostrati ma non navigabili; i file speciali non sono scaricabili. La copia di cartelle con link, file speciali o aree riservate viene rifiutata.

Configurazione: `CORA_FILE_ROOTS` contiene una lista JSON di risorse con `id`, `label`, `path`, `writable`. I percorsi relativi nella configurazione sono riferiti alla repository; quelli nelle richieste sono relativi alla risorsa selezionata. Se la configurazione è vuota viene creata soltanto `./data/server_files`, per prove locali. Le risorse esplicite mancanti vengono segnalate indisponibili senza creare cartelle. Lo spazio riportato è quello del filesystem che ospita la risorsa, non la somma dei suoi file.

Per Debian si può configurare `/` come “Questo server” in sola lettura e una risorsa distinta per i dati in scrittura; per Windows una cartella di prova o una radice in sola lettura. Gli esempi sono in `.env.example`. Non puntare le risorse scrivibili agli archivi interni gestiti da Immich o Nextcloud: le loro modifiche devono passare dai rispettivi servizi.

`CORA_FILES_TOKEN` protegge tutti questi endpoint con `Authorization: Bearer <token>`. Se vuoto sono ammesse soltanto richieste dirette dal loopback. **Prima di accesso remoto, anche attraverso un proxy locale o Tailscale, impostare il token**: un proxy locale può altrimenti far apparire locali richieste esterne. Il token non va salvato nel codice frontend o versionato. È una protezione provvisoria per il proprietario, non un sistema multiutente; il frontend dovrà gestirne l'inserimento prima di collegare la pagina.

Upload: spooling su disco e pubblicazione del file completo senza sovrascrittura. `CORA_FILES_MAX_UPLOAD_BYTES` limita il contenuto accettato (default 1 GiB); non sostituisce un limite sul corpo HTTP nel proxy. Le aree `.cora-staging` e `.cora-trash` sono escluse dalla navigazione API. Upload e cestino richiedono un filesystem compatibile e operazioni nello stesso volume: per un disco montato sotto una risorsa, configurare quel disco come risorsa autonoma.

Conflitti: `409`, percorsi non validi: `400`, accesso negato: `401/403`, elementi mancanti: `404`, upload eccessivo: `413`, filesystem/configurazione indisponibile: `503`. Il ripristino richiede che la cartella originale esista ancora. Il cestino occupa spazio; non sono esposte cancellazioni definitive.

Limiti della prima versione: un processo backend, operazioni serializzate; nessuna garanzia contro modifiche concorrenti dei percorsi da altri processi del server. Usare cartelle del proprietario e non directory modificabili da utenti non fidati. La paginazione limita la risposta ma l'elenco viene letto e ordinato interamente. Non sono ancora implementati ricerca ricorsiva, anteprime, condivisioni, ripresa upload, trasferimenti tra risorse o Libreria IA. Nessuna installazione sul server viene eseguita da questa modifica.

Verifica API senza caricare modelli: `python -m unittest discover -s tests -v` (richiede `httpx` per TestClient oltre alle dipendenze applicative).

## Interfaccia

La UI principale è separata dal backend ed è realizzata con React + Vite.

Cartella:

```text
frontend/
```

L’interfaccia ora usa il progetto React + TypeScript di `Aleselva12/frontend`, incluso in questa cartella. Comprende Home, Chat, Architettura, Programma, Calendario, File, Attività e Impostazioni.

I collegamenti reali sono `/chat`, `/health` e `/capabilities`: risposta di Cora, thread separati, stato del backend/Ollama, modello supervisore, statistiche memoria e registro degli agenti. Le conversazioni della sidebar e gli esiti delle richieste restano nella memoria della pagina, fino al ricaricamento; non sono uno storico persistente del server.

La Home legge `/api/v1/server/telemetry` (CPU, RAM, GPU opzionale, dischi, rete, alimentazione e cronologia CPU), `/api/v1/server/storage` e `/api/v1/system/status`. Aggiornamento automatico, errori espliciti e sensori assenti mostrati come sconosciuti. Docker è interrogato in sola lettura se accessibile; gli URL di Immich, Nextcloud e n8n si configurano in `.env`. Dettagli e limiti in `frontend/COLLEGAMENTI.md`.

Le funzioni senza endpoint hanno avvisi permanenti “Collegamento da realizzare” e controlli disabilitati: file del NAS, allegati, calendario personale, editor, streaming, run, conferme, microfono, permessi e modifica della mappa. Non vengono visualizzati dati fittizi. Nessun agente calendario è stato aggiunto.

La mappa mostra agenti e capacità del registro reale; “Modulo presente” è disponibilità strutturale, non readiness runtime. I collegamenti della mappa illustrano delega possibile e non tracce eseguite.

Il dettaglio aggiornato è in `frontend/COLLEGAMENTI.md`, `frontend/README.md` e nelle Impostazioni. Vite usa `/backend` come proxy locale verso FastAPI su `127.0.0.1:8000`. Il target si configura in `frontend/.env.local` con `CORA_API_TARGET`; per un URL API diretto configurare anche `VITE_API_BASE_URL` e `CORA_UI_ORIGINS` sul backend.

Indirizzo predefinito:

```text
http://127.0.0.1:5173
```

Il file `app.py` contiene ancora la precedente interfaccia Streamlit ed è presente come alternativa/fallback nel proof of concept.

## AVVIO su Windows

Il punto di ingresso principale è:

```text
AVVIO.cmd
```

che esegue:

```text
AVVIO.ps1
```

Se Cora è già attiva, AVVIO apre direttamente l'interfaccia nel browser.

Se non è attiva, lo script può:

1. creare `.env` a partire da `.env.example` se manca;
2. verificare Ollama;
3. provare ad avviare Docker Desktop e il container `ia-ollama` quando necessario;
4. creare la virtualenv Python `.venv` se manca;
5. installare o aggiornare le dipendenze Python quando cambia `requirements.txt`;
6. avviare FastAPI sulla porta 8000;
7. installare o aggiornare il frontend quando cambia `package.json` o `package-lock.json`;
8. avviare Vite sulla porta 5173;
9. aprire automaticamente l'interfaccia.

Lo script gestisce file PID e un lock di avvio. Verifica che la pagina sia il nuovo frontend e segnala le porte occupate, senza terminare processi sconosciuti. Al primo avvio aggiornato chiudere le vecchie finestre Cora. Per usare un checkout frontend separato: `powershell -File AVVIO.ps1 -FrontendPath C:\percorso\frontend`.

Per creare un collegamento AVVIO sul desktop è presente:

```text
CREA_AVVIO_DESKTOP.ps1
```

## Avvio manuale

Dipendenze Python:

```bash
python -m venv .venv
pip install -r requirements.txt
```

Backend:

```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Frontend, in un secondo terminale:

```bash
cd frontend
npm install
npm run dev
```

## Configurazione

Il file:

```text
.env.example
```

contiene tutte le variabili attualmente previste per:

- Ollama;
- documenti locali;
- audio e trascrizioni;
- Whisper;
- diarizzazione;
- Gmail;
- preventivi PDF;
- limiti di lettura dei documenti;
- risorse, token proprietario e limite upload di File server.

Il file reale `.env` è escluso dal versionamento.

## Controllo del progetto

È presente uno smoke test non distruttivo:

```bash
python smoke_check.py
```

Controlla:

- sintassi dei file Python;
- import dei moduli principali;
- copertura del Permission Engine per le azioni implementate;
- configurazione rilevata per i componenti principali.

## Dipendenze principali

Backend e agenti:

- Python;
- LangChain;
- LangGraph;
- Ollama tramite `langchain-ollama`;
- FastAPI + Uvicorn;
- Streamlit;
- psutil;
- python-docx;
- pypdf;
- faster-whisper;
- pyannote.audio;
- Google API Client e librerie OAuth;
- ReportLab.

Frontend:

- React;
- React DOM;
- Vite;
- Lucide React.

## Vincoli e protezioni attuali

Nel codice attuale:

- i file locali sono accessibili solo nelle directory autorizzate;
- alcuni percorsi e file sensibili sono esplicitamente bloccati;
- `.env`, credenziali Gmail e token non devono essere versionati;
- il Local Research Agent non usa Internet;
- l'Email Agent non invia automaticamente email;
- il salvataggio di una bozza Gmail richiede una richiesta esplicita;
- il sistema non deve inventare risultati di tool o dati commerciali mancanti;
- il log runtime e il database della memoria sono esclusi da Git;
- la memoria volatile LangGraph e la memoria persistente SQLite sono due livelli distinti.

## Struttura essenziale

```text
serveria1/
├── AVVIO.cmd
├── AVVIO.ps1
├── CREA_AVVIO_DESKTOP.ps1
├── api.py
├── app.py
├── graph.py
├── prompt.py
├── tools.py
├── local_tools.py
├── smoke_check.py
├── requirements.txt
├── .env.example
├── core/
│   ├── logging.py
│   ├── memory.py
│   ├── orchestration.py
│   ├── permissions.py
│   └── plans.py
├── frontend/
├── structure_agent/
├── search_agent/
├── audio_agent/
└── email_agent/
```
