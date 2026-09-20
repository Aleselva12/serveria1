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
├── Local Research Agent
├── Audio Agent
└── Email & Quotes Agent
      ↓
Ollama locale
```

Il Supervisor è il punto centrale di ingresso. Riceve la richiesta dell'utente, può rispondere direttamente oppure delegare a uno strumento locale o a uno dei tre agenti specializzati.

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

Usa LangGraph e `MemorySaver` per mantenere lo stato della conversazione durante l'esecuzione. Non è presente una memoria persistente su database.

Il Supervisor può usare direttamente questi strumenti locali:

- calcolatrice per operazioni aritmetiche di base;
- lettura dello stato reale di CPU, RAM e disco;
- elenco dei file autorizzati della repository;
- lettura dei file testuali autorizzati della repository;
- lettura del registro centrale di struttura e capacità.

Può inoltre delegare ai tre agenti specializzati.

## Registro centrale di struttura e capacità

Il progetto contiene ora un nucleo condiviso:

```text
core/
├── capabilities.py
└── registry.py
```

`capabilities.py` definisce lo schema comune usato per descrivere componenti e capacità.

`registry.py` è la fonte centrale per sapere quali componenti sono definiti nel sistema. Registra attualmente il Supervisor, i tre agenti specializzati, i tool locali principali, il backend FastAPI e l'interfaccia React.

Per ogni componente sono descritti identificativo, nome, tipo, descrizione, capacità dichiarate, modulo associato e dipendenze strutturali.

Il registro può verificare se il modulo Python associato è disponibile e restituisce uno stato strutturale del componente. Questo controllo non sostituisce gli health check runtime dei servizi esterni.

Il Supervisor accede al registro tramite:

```text
structure_registry_tool
```

Il registro non implementa permessi, memoria persistente o logging avanzato.

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
- supporto a file testuali comuni e documenti Word `.docx`;
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

`/health` restituisce lo stato del backend, la raggiungibilità di Ollama, il modello configurato e l'elenco degli agenti letto dal registro centrale.

`/capabilities` restituisce il registro centrale dei componenti e delle capacità.

`/chat` riceve il messaggio dell'utente e un eventuale `thread_id`, invoca il grafo principale e restituisce la risposta di Cora.

Il backend locale usa di default:

```text
http://127.0.0.1:8000
```

## Interfaccia

La UI principale è separata dal backend ed è realizzata con React + Vite.

Cartella:

```text
frontend/
```

L'interfaccia attuale comprende:

- chat con Cora;
- creazione di una nuova conversazione;
- visualizzazione dei tre agenti disponibili;
- controllo periodico dello stato del backend;
- indicazione dello stato di Ollama;
- visualizzazione del modello locale configurato.

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
7. installare o aggiornare il frontend quando cambia `package.json`;
8. avviare Vite sulla porta 5173;
9. aprire automaticamente l'interfaccia.

Lo script gestisce inoltre file PID, un lock di avvio e la chiusura di processi rimasti sulle porte usate dal backend e dal frontend.

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
- limiti di lettura dei documenti.

Il file reale `.env` è escluso dal versionamento.

## Controllo del progetto

È presente uno smoke test non distruttivo:

```bash
python smoke_check.py
```

Controlla:

- sintassi dei file Python;
- import dei moduli principali;
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
- la memoria LangGraph presente è volatile e non costituisce una memoria persistente del sistema.

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
├── frontend/
├── search_agent/
├── audio_agent/
└── email_agent/
```
