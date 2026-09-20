# Cora Lab

Proof of concept locale del sistema multi-agente Cora.

Il progetto usa LangGraph come orchestratore e Ollama come runtime LLM locale. Il branch `ChatGPT` contiene il lavoro sperimentale attuale.

## Architettura attuale

```text
Cora / Supervisor
├── Local Research Agent
│   ├── ricerca nei documenti locali
│   ├── lettura Word .docx e file testuali
│   └── confronto e valutazione delle informazioni
├── Audio Agent
│   ├── trascrizione locale
│   ├── note vocali / riflessioni
│   ├── conversazioni a due interlocutori
│   └── riassunto e analisi su richiesta
└── Email Agent
    └── agente originale ancora da rivedere
```

Non è presente un agente di ricerca web. Il Local Research Agent lavora soltanto sui documenti autorizzati.

## Avvio rapido

```bash
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Copia poi:

```text
.env.example -> .env
```

e configura almeno Ollama e le directory locali.

Interfaccia principale:

```bash
streamlit run app.py
```

oppure terminale:

```bash
python chat.py
```

## Modello locale

Configurazione predefinita del proof of concept:

```env
OLLAMA_MODEL=gpt-oss:20b
OLLAMA_BASE_URL=http://localhost:11435
```

## Local Research Agent

La cartella autorizzata è definita da:

```env
CORA_KNOWLEDGE_ROOT=./knowledge
```

Supporta anche file Microsoft Word `.docx`.

L'agente deve distinguere tra rilevanza, importanza, supporto documentale e affidabilità, senza trattare automaticamente come vero tutto ciò che trova in un documento.

## Audio Agent

La cartella autorizzata è definita da:

```env
CORA_AUDIO_ROOT=./audio
```

La trascrizione usa `faster-whisper`. La separazione degli speaker usa opzionalmente un modello `pyannote` locale.

Vedi `audio_agent/README.md` per la configurazione completa.

## Sicurezza del proof of concept

- accesso a file limitato alle directory autorizzate;
- credenziali escluse dalla lettura locale e da Git;
- modelli e audio locali esclusi dal repository;
- nessuna ricerca web nel Local Research Agent;
- nessun upload audio richiesto dall'Audio Agent.

## Roadmap

La roadmap PC/server è documentata in `Cora_roadmap_PC_e_server.md`.
