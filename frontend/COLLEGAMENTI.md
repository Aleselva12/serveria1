# Collegamenti frontend ↔ backend Cora

Stato allineato al backend `serveria1/main` dopo l'integrazione del frontend.

## Collegati

Calendario: viste mese/giorno e CRUD persistente sotto `/api/v1/calendar`; storico, recupero eliminati e proposte degli agenti da approvare. `CORA_CALENDAR_TOKEN` richiesto per accesso remoto.

| Interfaccia | API reale | Limite attuale |
| --- | --- | --- |
| Chat | `POST /chat` con `{message, thread_id}` → `{response, thread_id}` | Risposta completa, nessuno streaming o allegato. |
| Home / Impostazioni | `GET /health` | FastAPI, raggiungibilità Ollama, modello supervisore, statistiche memoria. |
| Home | `GET /api/v1/server/telemetry`, `GET /api/v1/server/storage` | CPU/RAM/dischi/rete e cronologia reali; GPU e alimentazione solo se rilevabili. |
| Servizi Home | `GET /api/v1/system/status` | FastAPI, Ollama, Docker/container se accessibili; Immich/Nextcloud/n8n con URL configurato. Raggiungibilità, non readiness degli agenti. |
| Architettura | `GET /capabilities`, `GET /api/v1/architecture/graph`, `GET /api/v1/runs`, `GET /api/v1/runs/{id}` | Registro strutturale, topologia eseguibile versionata e tracce correlate persistenti. |
| Nuova chat / sidebar | `GET /conversations`, `GET /conversations/{id}/messages`, `POST /chat` | Storico PostgreSQL caricato all’apertura e alla selezione; aggiornamento manuale e dopo invio. Ultime 500 chat e 2.000 messaggi per chat. Nuove chat salvate al primo messaggio. |
| Attività | Esito HTTP delle richieste chat nella pagina | Non è un endpoint dei run, né una traccia degli agenti. |
| AVVIO | Launcher di `serveria1` con frontend integrato o `-FrontendPath` | Avvio locale Windows; nessuna configurazione automatica del NAS. |
| File server | `/api/v1/server/files/roots`, `/children`, `/upload`, `/download`, `/folders`, `/transfer`, `/trash`, `/restore` | Risorse configurate, ricerca nomi nella cartella, paginazione, upload multipli, gestione file e cestino. |
| Libreria IA | `/api/v1/library/files/*`, `/import`, `/upload` | Cartella separata, copie dal server; upload salva anche un originale sul server. |


## Da realizzare — avvisi permanenti nella UI

| Area | Collegamenti da completare | Promemoria tecnico |
| --- | --- | --- |
| Chat | Streaming, polling e ripresa dopo disconnessione | `/runs/{id}/events`, fallback `/runs/{id}`. |
| Chat | Allegati, upload e associazione alla richiesta | `/files`, `attachmentIds`; la graffetta resta disabilitata. |
| Architettura | Modifica e pubblicazione del grafo | Grafo eseguibile e tracce ora collegati; API di modifica ancora da progettare. |
| Attività | Lista run, passi, log, errori, anteprime e approvazioni | `/runs`, `/approvals/{id}`; evitare approvazioni implicite. |
| Programma | Workspace consentiti, albero file, lettura | `/workspaces`, `/workspaces/{id}/files`, `/file?path=...`. |
| Programma | Scrittura, revisione/conflitti, audit | `PUT /workspaces/{id}/file` con revisione, permessi server. |
| Programma | Esecuzione autorizzata, output, timeout/cancellazione | `/workspaces/{id}/executions`, `/executions/{id}`; comandi consentiti. |
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

## File: sottopagine collegate

“File server” e “Libreria IA” sono su una riga subito sotto il titolo “File” e usano la stessa grafica. I contratti backend sono nel README principale. Il token di “Accesso ai file” resta in memoria, non in localStorage, URL o bundle. Download autenticato tramite fetch e URL blob; upload con FormData senza imporre Content-Type. Le mutazioni non vengono ritentate automaticamente. La cartella degli originali degli upload IA è esposta in File server come “Originali Libreria IA”. Nessuno scambio al riavvio è implementato.

## Da verificare dopo l'installazione sul server — visibilità dei file

Problema segnalato dall'utente: al momento i file non sembrano visibili nella pagina. La causa non è ancora verificata. La verifica e l'eventuale correzione sono rinviate all'installazione sul server: l'obiettivo è vedere le cartelle reali del server Debian, non quelle del PC o dell'ambiente di sviluppo.

- Configurare `CORA_FILE_ROOTS` con i percorsi desiderati sul server (radice `/` e cartelle dei dati autorizzate; riferimento NAS: `/srv/nas/Dati/drive`).
- Verificare disponibilità dei dischi montati, permessi dell'utente che esegue il backend ed eventuali volumi Docker.
- Verificare accesso tramite Tailscale, token File server e risultati delle API `/roots` e `/children`, distinguendo un errore da una cartella realmente vuota.
- Configurare e verificare anche `CORA_KNOWLEDGE_ROOT` e `CORA_LIBRARY_ORIGINALS_ROOT` sui percorsi reali del server.

Questo punto resta aperto fino alla prova sul server. Non sono richiesti interventi sui percorsi locali per chiuderlo.

# Architettura — Tools

La pagina Architettura ha due sezioni: Architettura conserva la mappa degli agenti; Tools mostra nodi singoli selezionabili, dettagli ed elenco per funzione con ricerca e filtri. Il catalogo arriva da `GET /tools/inventory` e non contiene dati simulati.

L’inventario ispeziona le dichiarazioni Python e le liste di tool collegate ai grafi, senza caricare modelli o eseguire strumenti. Le API effettivamente registrate da FastAPI sono mostrate separatamente come operazioni backend non direttamente assegnate agli agenti. Le predisposizioni sono marcate come non implementate nella versione osservata. La rilevazione calendario include i moduli `*tools.py` nella radice, nel core e nelle cartelle degli agenti; una lista calendario importata e aggiunta al Supervisor viene risolta dal catalogo.

Gli stati descrivono collegamenti strutturali, non readiness runtime, credenziali o autorizzazioni. Automazioni, editor dei flussi ed esecuzione non vengono attivati da questa pagina. I nodi sono in sola lettura, senza collegamenti fittizi fra strumenti.
