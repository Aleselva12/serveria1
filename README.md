# Cora Lab

Proof of concept locale del sistema multi-agente Cora.

Il progetto usa LangGraph come orchestratore e Ollama come runtime LLM locale. Il branch `ChatGPT` contiene il lavoro sperimentale attuale.

## Architettura attuale

```text
React / Vite
      ↓
FastAPI
      ↓
Cora / Supervisor
├── Local Research Agent
├── Audio Agent
└── Email & Quotes Agent
```

## AVVIO

Su Windows il punto d'ingresso principale è:

```text
AVVIO.cmd
```

Se l'interfaccia è già attiva, AVVIO la apre nel browser.

Se Cora non è attiva, AVVIO prova a:

1. creare `.env` da `.env.example` se manca;
2. avviare il container Docker `ia-ollama` se Ollama non risponde;
3. creare la virtualenv Python se manca;
4. installare/aggiornare le dipendenze solo quando `requirements.txt` cambia;
5. avviare FastAPI;
6. installare/aggiornare il frontend solo quando `package.json` cambia;
7. avviare React/Vite;
8. aprire automaticamente l'interfaccia.

Per creare un vero collegamento **AVVIO** sul desktop esegui una volta:

```powershell
powershell -ExecutionPolicy Bypass -File .\CREA_AVVIO_DESKTOP.ps1
```

## Interfaccia

La nuova UI usa **React + Vite** ed è separata dal backend. Questo permette di cambiare liberamente grafica e funzioni senza modificare il cuore di Cora.

Frontend:

```text
frontend/
```

Backend API:

```text
api.py
```

API principali:

```text
GET  /health
POST /chat
```

La vecchia UI Streamlit in `app.py` resta temporaneamente disponibile come fallback durante il proof of concept.

## Installazione manuale

Se non vuoi usare AVVIO:

```bash
python -m venv .venv
pip install -r requirements.txt
```

Poi:

```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

e, in un secondo terminale:

```bash
cd frontend
npm install
npm run dev
```

Interfaccia:

```text
http://127.0.0.1:5173
```

## Modello locale

Configurazione predefinita:

```env
OLLAMA_MODEL=gpt-oss:20b
OLLAMA_BASE_URL=http://localhost:11435
```

## Local Research Agent

Ricerca, legge e confronta documenti locali autorizzati, inclusi file Word `.docx`.

```env
CORA_KNOWLEDGE_ROOT=./knowledge
```

## Audio Agent

Trascrive audio locali con `faster-whisper`, con diarizzazione opzionale tramite modello `pyannote` locale.

```env
CORA_AUDIO_ROOT=./audio
```

## Email & Quotes Agent

Gestisce ricerca nell'archivio Gmail, digest giornalieri, bozze email e preventivi PDF.

La generazione PDF è una base funzionale; i preventivi saranno automatizzati collegando cataloghi, listini, dati cliente, varianti e condizioni commerciali.

## Controllo progetto

Dopo modifiche importanti:

```bash
python smoke_check.py
```

## Sicurezza del proof of concept

- accesso file limitato alle directory autorizzate;
- credenziali escluse da Git;
- modelli, audio, documenti e preventivi esclusi dal repository;
- nessuna ricerca web nel Local Research Agent;
- nessun invio automatico di email;
- nessun dato commerciale mancante viene inventato.

## Roadmap

Vedi `Cora_roadmap_PC_e_server.md`.
