# Collegamenti frontend ↔ backend Cora

Stato allineato al backend `serveria1/main` dopo l'integrazione del frontend.

## Collegati

| Interfaccia | API reale | Limite attuale |
| --- | --- | --- |
| Chat | `POST /chat` con `{message, thread_id}` → `{response, thread_id}` | Risposta completa, nessuno streaming o allegato. |
| Home / Impostazioni | `GET /health` | FastAPI, raggiungibilità Ollama, modello supervisore, statistiche memoria. |
| Home | `GET /api/v1/server/telemetry`, `GET /api/v1/server/storage` | CPU/RAM/dischi/rete e cronologia reali; GPU e alimentazione solo se rilevabili. |
| Servizi Home | `GET /api/v1/system/status` | FastAPI, Ollama, Docker/container se accessibili; Immich/Nextcloud/n8n con URL configurato. Raggiungibilità, non readiness degli agenti. |
| Architettura | `GET /capabilities` | Registro strutturale, capacità e disponibilità moduli; non health runtime degli agenti. |
| Nuova chat / sidebar | Thread separati tramite `/chat` | Lista e messaggi in memoria nella pagina; spariscono al refresh. |
| Attività | Esito HTTP delle richieste chat nella pagina | Non è un endpoint dei run, né una traccia degli agenti. |
| AVVIO | Launcher di `serveria1` con frontend integrato o `-FrontendPath` | Avvio locale Windows; nessuna configurazione automatica del NAS. |

## Da realizzare — avvisi permanenti nella UI

| Area | Collegamenti da completare | Promemoria tecnico |
| --- | --- | --- |
| Chat | Storico persistente, creazione/lista conversazioni, recupero messaggi | `/api/v1/conversations` e relativi messaggi; non confondere memoria SQLite con storico chat. |
| Chat | Streaming, polling e ripresa dopo disconnessione | `/runs/{id}/events`, fallback `/runs/{id}`. |
| Chat | Allegati, upload e associazione alla richiesta | `/files`, `attachmentIds`; la graffetta resta disabilitata. |
| Architettura | Grafo backend versionato e traccia reale dei passi | `/architecture/graph`, `/agents`, `/runs`; il registro ora è letto da `/capabilities`. |
| Attività | Lista run, passi, log, errori, anteprime e approvazioni | `/runs`, `/approvals/{id}`; evitare approvazioni implicite. |
| Programma | Workspace consentiti, albero file, lettura | `/workspaces`, `/workspaces/{id}/files`, `/file?path=...`. |
| Programma | Scrittura, revisione/conflitti, audit | `PUT /workspaces/{id}/file` con revisione, permessi server. |
| Programma | Esecuzione autorizzata, output, timeout/cancellazione | `/workspaces/{id}/executions`, `/executions/{id}`; comandi consentiti. |
| Calendario | Eventi personali CRUD persistenti | `/calendar/events`; nessun agente calendario e nessuna scrittura solo nel browser. |
| File server | Collegare risorse, cartelle, filtro nomi/paginazione e spazio | Backend pronto: `GET /api/v1/server/files/roots`, `/children`; UI ancora da collegare. |
| File server | Collegare upload, download, cartelle, copia/spostamento e cestino | Backend pronto: `/api/v1/server/files/upload`, `/download`, `/folders`, `/transfer`, `/trash`, `/restore`. Condivisioni ancora da costruire. |
| Libreria IA | Raccolte, associazione documenti, elaborazioni e accesso degli agenti | Backend dedicato ancora da costruire; File server non indicizza documenti. |
| File server | Anteprime e ricerca ricorsiva | Backend ancora da costruire. |
| Audio | Acquisizione microfono, upload, trascrizione e speaker | Contratto dedicato da definire; il microfono resta disabilitato. |
| Impostazioni | Configurazione pubblica completa, modelli per ruolo, permessi utente | `/system/config`, `/permissions`; il registro non è un manifesto permessi utente. |
| Sessioni | Autenticazione, protezione delle mutazioni e accesso remoto | Da definire prima di una pubblicazione remota. |
| Architettura modificabile | Bozze, validazione, simulazione/pubblicazione e rollback | Contratti dedicati versionati; mappa sola lettura. |

I percorsi `/api/v1` delle sezioni da realizzare sono proposte; le tre API di monitoraggio Home sono implementate. La UI non prova mutazioni inesistenti e non mostra dati demo come reali. Le voci sono centralizzate in `src/services/connections.ts` e mostrate nelle Impostazioni, anche con il backend online.

“Collegamento da realizzare” indica lavoro futuro. “Collegamento non riuscito” indica un errore attuale di rete/API su un collegamento esistente. Dopo un errore di chat non viene ripetuta automaticamente la richiesta: il backend potrebbe aver già iniziato l’elaborazione.

## Monitoraggio Home

CPU/RAM/rete/dischi vengono letti con psutil ogni 5 secondi quando la Home è aperta; servizi ogni 15 secondi. CPU e velocità di rete richiedono due campioni; CPU conserva gli ultimi 120 campioni in memoria nel processo backend. In caso di errore i valori precedenti vengono rimossi. Il traffico è la somma delle interfacce attive diverse dal loopback; interfacce virtuali possono contabilizzare lo stesso traffico.

GPU AMD: sysfs Linux; GPU NVIDIA: nvidia-smi se presente. Altri driver mostrano “Non disponibile”. Alimentazione: sensore batteria del sistema, se esposto; nessuna inferenza sulla presenza di UPS o consumo in watt.

Docker viene interrogato in sola lettura con `docker ps -a`, senza modificare privilegi o montare socket. Immich, Nextcloud e n8n usano gli URL di controllo configurati in `.env` (`CORA_SERVICE_IMMICH_URL`, `CORA_SERVICE_NEXTCLOUD_URL`, `CORA_SERVICE_N8N_URL`). URL vuoto significa “Non verificato”. Nessuna operazione di avvio/arresto viene esposta. Le metriche descrivono il sistema visibile al processo backend; in Docker la visibilità di dischi/sensori dipende dal container.

Verifica: `python -m unittest discover -s tests -v`, `npm test --prefix frontend`, `npm run build --prefix frontend`.

## File: separazione delle sottopagine

Scelta concordata: “File server” e “Libreria IA”, su una riga subito sotto il titolo “File”, con grafica condivisa. Per ora è implementato solo il backend File server, documentato nel README principale. Il frontend resta da collegare. Tutti gli endpoint richiedono `Authorization: Bearer <CORA_FILES_TOKEN>` quando configurato; non inserire token nel bundle o nelle variabili VITE pubbliche. Il download autenticato dovrà usare fetch con header e poi un URL blob, non un semplice link senza autenticazione. Le mutazioni non vanno ritentate automaticamente dopo timeout. L'upload usa multipart/FormData, quindi il client deve lasciare al browser il Content-Type con boundary.
