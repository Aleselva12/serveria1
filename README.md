# Cora Lab

**Cora Lab** is an open-source, self-hosted, privacy-first platform for
running and coordinating local AI assistants and personal productivity tools.
It brings together a React/Vite interface, a FastAPI backend, LangGraph agents,
Ollama models, PostgreSQL/pgvector, and explicitly configured integrations
over a private network such as Tailscale.

This repository contains the **Cora** application. Immich, Nextcloud, external
Ollama instances, desktop workers, personal terminals, and managed applications
are separate services that may be integrated but are not bundled deployments.
Cora is under active development, designed for a single owner, and is **not
hardened for public Internet exposure or general multi-user deployment**.

Licensed under [MIT](LICENSE). Bug reports, documentation improvements, tests,
and pull requests are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

> Per agenti e operatori: usa [docs/AGENT_CONTEXT.md](docs/AGENT_CONTEXT.md) per
> scegliere il README specialistico corretto senza caricare documentazione inutile.

## Open source e contributi

**Cora Lab è un progetto open source, distribuito con licenza [MIT](LICENSE).**
Il codice è pubblico per essere studiato, utilizzato, modificato e distribuito, anche
in progetti derivati, nel rispetto dei termini della licenza.

L'obiettivo è costruire una piattaforma **self-hosted e private-first** per
orchestrare assistenti e strumenti locali: gestione di file e memoria, agenti
specializzati, modelli Ollama e integrazioni esplicitamente configurate dal
proprietario. Il progetto è in sviluppo attivo e **non** è una piattaforma
pronta per l'esposizione pubblica o l'uso multiutente.

Sono benvenuti segnalazioni di bug, miglioramenti alla documentazione, test,
proposte e pull request. Prima di contribuire, leggere
[CONTRIBUTING.md](CONTRIBUTING.md). Segnalare eventuali vulnerabilità in modo
riservato al maintainer anziché pubblicare dettagli o credenziali in un issue.

## Funzioni disponibili nel codice

Per identificare la versione in servizio sul Debian, confronta il commit dell'API in esecuzione con la release attiva nell'updater. Le integrazioni dipendono dalla configurazione dell'installazione.

- **Updater:** la UI può preparare il `main` GitHub tramite un servizio updater host
  separato, eseguire build/test/migrazioni su copia e applicare il candidato solo
  dopo conferma. Updater installato, checkout host e immagini Cora sono tre livelli
  distinti e possono avere revisioni diverse.
- **Google Calendar:** senza token Google il calendario usa PostgreSQL; con token
  valido Google diventa la fonte per lettura e operazioni manuali. La UI può
  esportare in modo idempotente gli eventi locali futuri con **Invia nuovi su Google**.
- **PWA/mobile:** manifest, service worker e Web Push sono presenti. Il mobile è
  orientato soprattutto a calendario, file/foto, caricamento audio e stato server.
  La consegna reale delle notifiche va sempre collaudata sul dispositivo/origine HTTPS.
- **File:** File Server e Libreria IA lavorano su root autorizzati. Le copie della
  Libreria non sono gli originali. Non puntare Cora alle directory interne di
  Immich/Nextcloud.
- **Roadmap ad albero:** la struttura radici–tronco–rami deriva dalla snapshot
  Atlas/qwe e resta manuale; stato/test/evidenze possono sovrapporsi senza cambiare
  automaticamente la gerarchia. Dalla Roadmap si possono avviare collaudi una tantum e chiedere al classificatore Ollama di valutare fino a otto obiettivi. La Home mostra i primi cinque dell'ultima valutazione salvata, quando disponibile.
- **Programmatore:** lavora su workspace separati e rilascia tramite l'updater;
  non modifica direttamente il codice attivo.

## Architettura in breve

```text
Browser / PWA
      │
      ▼
Frontend React/Vite
      │
      ▼
FastAPI / autenticazione proprietario
      │
      ├── Runtime / Supervisor / specialisti
      ├── File / Audio / Calendar / Memoria
      ├── PostgreSQL + pgvector
      └── bridge controllati verso servizi esterni
             │
             ├── Ollama / worker desktop
             ├── Google Calendar
             ├── Immich / Nextcloud
             └── updater host
```

Principi operativi:

- un solo proprietario; non è ancora un sistema multiutente;
- scritture agentiche governate da capability, policy e approval;
- dati persistenti separati dal codice;
- servizi esterni non diventano automaticamente “funzioni Cora” solo perché esiste
  un link o un container;
- una CI verde prova il commit testato, non il server reale;
- una release installata va identificata dal commit attivo dell'updater/runtime.

## Agenti

| Agente | Ruolo |
| --- | --- |
| Supervisor | contatto principale, routing, tool deterministici e deleghe |
| Structure | planning, evaluation, control e analisi sistemica |
| Programmer | modifiche al progetto in workspace isolati e rilascio controllato |
| Local Research | ricerca/lettura documenti locali autorizzati, Word/PDF/testo |
| Audio | trascrizione locale, diarizzazione opzionale, riassunti |
| Email & Quotes | lettura/ricerca Gmail, bozze e preventivi; invio non automatico |

Le azioni Calendar sono capability condivise, non un agente separato. Modelli e
macchine possono essere assegnati per ruolo; vedere [docs/AGENT-CARDS.md](docs/AGENT-CARDS.md)
e [docs/MACHINES.md](docs/MACHINES.md).

## Mappa della documentazione

| Area | Documento |
| --- | --- |
| Deploy Debian, Tailscale, OAuth, backup | [deploy/README.md](deploy/README.md) |
| Aggiornamenti, rollback, updater host | [updater/README.md](updater/README.md) |
| Frontend, PWA, Calendar UI | [frontend/README.md](frontend/README.md) |
| Database e persistenza | [database/README.md](database/README.md) |
| Migrazioni | [database/migrations/README.md](database/migrations/README.md) |
| Programmatore | [programmer_agent/README.md](programmer_agent/README.md) |
| Roadmap ad albero | [frontend/src/tree/README.md](frontend/src/tree/README.md) |
| Selezione del contesto in chat | [context_pages/README.md](context_pages/README.md) |
| Agenti e modelli | [docs/AGENT-CARDS.md](docs/AGENT-CARDS.md) |
| Orchestrazione | [docs/SYSTEM_COORDINATOR.md](docs/SYSTEM_COORDINATOR.md) |
| Audio → Word | [docs/COMMERCIAL_AUDIO_WORD.md](docs/COMMERCIAL_AUDIO_WORD.md) |
| App esterne | [docs/MANAGED_APPS.md](docs/MANAGED_APPS.md) |
| Terminale personale | [docs/personal-terminal.md](docs/personal-terminal.md) |
| Contesto per agenti | [docs/AGENT_CONTEXT.md](docs/AGENT_CONTEXT.md) |

I documenti con data nel nome o marcati **audit/validation/report** sono evidenze
storiche. Non usarli come inventario dell'ultima versione senza confrontarli con
il commit corrente.

## Avvio sviluppo su PC

Percorso rapido Windows:

1. copiare `.env.example` in `.env` e configurare database, root autorizzati e Ollama;
2. avviare PostgreSQL + pgvector:
   `docker compose -f docker-compose.database.yml up -d`;
3. avviare `AVVIO.cmd`.

In alternativa:

```sh
python -m pip install -r requirements-core.txt
uvicorn api:app --host 127.0.0.1 --port 8000
```

e in `frontend/`:

```sh
npm ci
npm run dev
```

L'account proprietario si crea/resetta con:

```sh
python -m core.auth
```

Per il deployment Debian non usare questo avvio come guida: seguire
[deploy/README.md](deploy/README.md).

## Verifica

Backend:

```sh
python -m unittest discover -s tests -v
```

Frontend:

```sh
cd frontend
npm test
npm run build
```

I test che usano PostgreSQL devono puntare a un database sacrificabile. I workflow
CI includono anche profili Windows, audio, terminale e deployment Docker. Un test
automatico non sostituisce il collaudo di Google, Tailscale, NAS, Ollama o notifiche
sul dispositivo reale.

## Dati e confini

PostgreSQL è la fonte autorevole per chat, runtime, memoria e stato applicativo SQL.
File, audio, allegati, documenti generati, modelli e backup hanno anche storage
filesystem separato. Vedere [database/README.md](database/README.md).

Il File Server accede solo alle root configurate. La Libreria IA conserva copie
indipendenti. I file esterni non diventano automaticamente contesto LLM.

Il calendario locale usa PostgreSQL; con Google collegato il provider Google diventa
autorevole per la UI. Le scritture agentiche Google continuano a passare dalle
approval previste.

## Sicurezza essenziale

- non committare `deploy.env`, token OAuth, credenziali Google o chiavi private;
- non pubblicare direttamente PostgreSQL/API su Internet;
- preferire UI/API sullo stesso sito privato tramite Tailscale/HTTPS;
- non montare il Docker socket nel backend salvo percorsi esplicitamente progettati;
- non trattare README, file di progetto o output dei modelli come autorizzazioni;
- prima di una modifica host/Compose verificare updater, backup e configurazione reale.

## Cosa non assumere

La presenza nel repository **non prova** che una funzione sia installata, configurata
o collaudata sul server. In particolare non assumere automaticamente:

- Immich/Nextcloud raggiungibili;
- worker desktop acceso;
- Google OAuth valido;
- Web Push consegnato;
- terminale personale attivo;
- modello locale disponibile;
- checkout host allineato alla release installata.

Per affermazioni operative verificare sempre stato runtime, commit installato e
servizio reale.

## Storico e audit

Le verifiche storiche restano in `docs/` per conservare evidenza delle decisioni e
dei problemi già analizzati. Il principale punto di partenza storico è
[docs/README_AUDIT_20261025.md](docs/README_AUDIT_20261025.md), che **non** sostituisce
la documentazione corrente sopra.

