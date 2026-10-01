# Collegamenti frontend ↔ backend Cora

Stato allineato al backend `serveria1/main` dopo l'integrazione del frontend.

## Collegati

| Interfaccia | API reale | Limite attuale |
| --- | --- | --- |
| Chat | `POST /chat` con `{message, thread_id}` → `{response, thread_id}` | Risposta completa, nessuno streaming o allegato. |
| Home / Impostazioni | `GET /health` | FastAPI, raggiungibilità Ollama, modello supervisore, statistiche memoria. Nessuna telemetria. |
| Architettura | `GET /capabilities` | Registro strutturale, capacità e disponibilità moduli; non health runtime degli agenti. |
| Nuova chat / sidebar | Thread separati tramite `/chat` | Lista e messaggi in memoria nella pagina; spariscono al refresh. |
| Attività | Esito HTTP delle richieste chat nella pagina | Non è un endpoint dei run, né una traccia degli agenti. |
| AVVIO | Launcher di `serveria1` con frontend integrato o `-FrontendPath` | Avvio locale Windows; nessuna configurazione automatica del NAS. |

## Da realizzare — avvisi permanenti nella UI

| Area | Collegamenti da completare | Promemoria tecnico |
| --- | --- | --- |
| Home | CPU, RAM, temperature, GPU opzionale, dischi, rete, cronologia e alimentazione/UPS | `GET /api/v1/server/telemetry`, `/server/storage`; `system_status_tool` esiste in Python ma non è un endpoint HTTP. |
| Servizi | Docker, supervisor occupato/errori, servizi extra | `GET /api/v1/system/status` con readiness reale. |
| Chat | Storico persistente, creazione/lista conversazioni, recupero messaggi | `/api/v1/conversations` e relativi messaggi; non confondere memoria SQLite con storico chat. |
| Chat | Streaming, polling e ripresa dopo disconnessione | `/runs/{id}/events`, fallback `/runs/{id}`. |
| Chat | Allegati, upload e associazione alla richiesta | `/files`, `attachmentIds`; la graffetta resta disabilitata. |
| Architettura | Grafo backend versionato e traccia reale dei passi | `/architecture/graph`, `/agents`, `/runs`; il registro ora è letto da `/capabilities`. |
| Attività | Lista run, passi, log, errori, anteprime e approvazioni | `/runs`, `/approvals/{id}`; evitare approvazioni implicite. |
| Programma | Workspace consentiti, albero file, lettura | `/workspaces`, `/workspaces/{id}/files`, `/file?path=...`. |
| Programma | Scrittura, revisione/conflitti, audit | `PUT /workspaces/{id}/file` con revisione, permessi server. |
| Programma | Esecuzione autorizzata, output, timeout/cancellazione | `/workspaces/{id}/executions`, `/executions/{id}`; comandi consentiti. |
| Calendario | Eventi personali CRUD persistenti | `/calendar/events`; nessun agente calendario e nessuna scrittura solo nel browser. |
| File | Albero cartelle, contenuti, ricerca/paginazione e storage NAS | `/server/files/tree`, `/folders/{id}/children`, `/server/storage`. |
| File | Upload, download, eliminazione/cestino, condivisioni | `/files`, `/download`, `/server/files/{id}`, `/shares`. |
| File | Anteprime, processamento e collegamento artefatti ai run | `/preview`, `/processing`, `sourceRunId` e `conversationId`. |
| Audio | Acquisizione microfono, upload, trascrizione e speaker | Contratto dedicato da definire; il microfono resta disabilitato. |
| Impostazioni | Configurazione pubblica completa, modelli per ruolo, permessi utente | `/system/config`, `/permissions`; il registro non è un manifesto permessi utente. |
| Sessioni | Autenticazione, protezione delle mutazioni e accesso remoto | Da definire prima di una pubblicazione remota. |
| Architettura modificabile | Bozze, validazione, simulazione/pubblicazione e rollback | Contratti dedicati versionati; mappa sola lettura. |

I percorsi `/api/v1` sono proposte del README, non API oggi presenti. La UI non prova mutazioni inesistenti e non mostra dati demo come reali. Le voci sono centralizzate in `src/services/connections.ts` e mostrate nelle Impostazioni, anche con il backend online.

“Collegamento da realizzare” indica lavoro futuro. “Collegamento non riuscito” indica un errore attuale di rete/API su un collegamento esistente. Dopo un errore di chat non viene ripetuta automaticamente la richiesta: il backend potrebbe aver già iniziato l’elaborazione.
