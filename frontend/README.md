# Cora Frontend

Interfaccia React + TypeScript + Vite basata sul design Figma, collegata al backend di Cora in `serveria1`. Sostituisce la precedente interfaccia. Le schermate mantengono lo stile e il layout della nuova repository; la mappa degli agenti resta in sola lettura.

## Cosa funziona adesso

- Chat reale: `POST /chat`, con `message` e `thread_id`, risposta completa al termine, attesa visibile, gestione errori e blocco degli invii duplicati.
- Nuove chat e selezione delle conversazioni di **questa sessione**, con thread separati. Nessuna persistenza del frontend al ricaricamento; il contesto LangGraph resta volatile sul backend.
- Stato FastAPI e raggiungibilità Ollama: `GET /health`, controllo ogni 15 secondi e pulsante di aggiornamento.
- Modello del supervisore e conteggio memorie, quando restituiti da `/health`.
- Architettura: agenti e capacità letti da `GET /capabilities`. Le linee rappresentano la delega possibile del supervisore, non tracce runtime o un grafo versionato ricevuto dal server. “Modulo presente” indica disponibilità strutturale, non readiness operativa.
- Attività: esito delle richieste chat inviate da questa pagina nella sessione corrente. Le tracce interne degli agenti sono da collegare.

## Collegamenti ancora mancanti

Ogni parte non esposta dal backend ha un avviso permanente **“Collegamento da realizzare”**, con pulsanti disabilitati. Backend offline, errore HTTP e funzione assente sono stati distinti. Nessun valore demo, file inventato, evento locale o risposta predefinita viene presentato come dato del server.

L’elenco completo è in [COLLEGAMENTI.md](COLLEGAMENTI.md), nelle Impostazioni dell’app e in `src/services/connections.ts`. Include telemetria, altri servizi, storico chat, streaming, allegati, file del NAS, editor, calendario personale, tracce, conferme, microfono, permessi e modifica della mappa. **Non è stato creato un agente calendario.**

## Avvio completo consigliato

Scaricare il branch **ChatGPT** aggiornato di `Aleselva12/serveria1`: contiene questa interfaccia nella cartella `frontend/`. Estrarre tutto e fare doppio clic su **AVVIO.cmd nella radice di serveria1**. Il launcher controlla/avvia backend, frontend e Ollama come nella configurazione esistente. Al primo avvio servono Python, Node.js/npm, Internet per le dipendenze e il modello locale configurato. Chiudere le vecchie finestre Cora prima del primo avvio aggiornato, se occupano le stesse porte.

Questa repository separata può essere usata anche accanto al backend:

```text
cartella-di-lavoro/
  serveria1/    # branch ChatGPT aggiornato
  frontend/    # questa repository
```

`AVVIO.cmd` qui cerca il launcher aggiornato in `../serveria1` e gli passa questa cartella come `FrontendPath`. Si può indicare un altro checkout con la variabile Windows `CORA_BACKEND_PATH`. Se il backend non è presente, avvia solo Vite: l’app segnala il backend offline finché FastAPI non viene avviato o configurato come servizio remoto.

## Configurazione del collegamento

Senza configurazione aggiuntiva, Vite serve l’app su `http://127.0.0.1:5173` e inoltra `/backend/*` a FastAPI su `http://127.0.0.1:8000`, rimuovendo il prefisso. Le API esistenti **non** usano `/api/v1`.

Per usare FastAPI su un altro PC o sul NAS, copiare `.env.example` in `.env.local`, cambiare `CORA_API_TARGET` con l’indirizzo raggiungibile e riavviare Vite:

```dotenv
VITE_API_BASE_URL=/backend
CORA_API_TARGET=http://INDIRIZZO_DEL_SERVER:8000
```

FastAPI deve essere in ascolto sull’interfaccia di rete corretta. Questo modifica il collegamento della UI, non installa o configura automaticamente il server fisico.

Per chiamare FastAPI direttamente si può impostare `VITE_API_BASE_URL` all’URL dell’API; in quel caso configurare `CORA_UI_ORIGINS` nel `.env` backend. Nessun segreto nelle variabili `VITE_`. L’integrazione mantiene il perimetro locale esistente: non aggiunge autenticazione né pubblicazione su Internet.

```bash
npm ci --include=dev
npm run dev
npm run build
npm test
```

`npm run build` verifica TypeScript e produce `dist/`. `npm run preview` usa lo stesso proxy per la verifica locale. Per servire `dist/` in produzione occorre configurare un reverse proxy `/backend`, oppure un URL API e CORS appropriati: il proxy Vite non viene incluso nei file statici.

## File principali

- `src/services/api.ts`: unico confine HTTP, per `/health`, `/capabilities`, `/chat`; valida payload e mostra errori espliciti.
- `src/services/useBackend.ts`: controlli periodici indipendenti per stato e registro, senza riutilizzare dati scaduti dopo un errore.
- `src/services/connections.ts`: promemoria centralizzati dei collegamenti mancanti.
- `src/components/ConnectionNotice.tsx`: avviso permanente uniforme.
- `src/components/Architecture.tsx`: visualizzazione del registro reale, senza tracce inventate.
- `src/App.tsx`, `Home.tsx`, `FileManager.tsx`: pagine e controlli della UI.
- `vite.config.ts`: proxy configurabile verso FastAPI.

La matrice seguente resta il **contratto futuro proposto**: i suoi endpoint non sono attivati automaticamente. Le tre API realmente collegate sono quelle elencate sopra.

## Contratto HTTP proposto, completo per la UI attuale

Base configurabile con `VITE_API_BASE_URL`; prefisso `/api/v1`. JSON UTF-8, identificativi stabili, timestamp ISO 8601 con fuso, paginazione per liste estese, errori strutturati `{code,message,requestId,details?}`. Le URL e i payload vanno concordati con FastAPI prima dell'attivazione. `src/services/api.ts` contiene solo le tre API reali: tutti i contratti futuri di questa tabella richiedono endpoint backend e nuovi metodi nell’adapter.

| Area e file frontend | Richiesta/evento previsto | Risposta o effetto richiesto |
| --- | --- | --- |
| Home `components/Home.tsx`/`api.ts` | `GET /server/telemetry`, `GET /server/storage` | CPU/RAM/GPU opzionale, temperature disponibili, dischi con byte usati/totali, rete con rate in bit/s, alimentazione/UPS opzionale, cronologia CPU, `sampledAt`; valori null o stale devono apparire come sconosciuti, mai come sani. Non usare nomi hardware del Figma come dati reali. |
| Stato `App.tsx`/`api.ts` | `GET /system/status` | Stato e ultimo controllo di FastAPI, Ollama, supervisor e servizi disponibili; distinguere offline, errore, occupato. |
| Impostazioni `App.tsx`/`api.ts` | `GET /system/config` | Modello effettivo, capability abilitate, configurazione pubblica; mai segreti, prompt riservati o credenziali. |
| Impostazioni/Programma, *da aggiungere* | `GET /permissions` | Capability per utente e area di lavoro: `OBSERVE`, `READ`, `DRAFT`, `WRITE`, `EXECUTE`, `ADMIN`; policy `AUTO`, `CONFIRM`, `BLOCKED`, radici consentite. L'interfaccia le rappresenta; il server le applica. |
| Chat `App.tsx`/`api.ts` | `GET /conversations`, `POST /conversations` | Elenco, nuova conversazione, ID, titolo e aggiornamento. Aggiungere rinomina/eliminazione solo quando decise. |
| Chat `App.tsx`/`api.ts` | `GET /conversations/{id}/messages`, `POST /conversations/{id}/messages` con `{content,attachmentIds}` | Messaggi ordinati, ID persistenti, ruolo, timestamp, allegati e `runId` per seguire l'esecuzione. Validare ID e dimensioni. |
| Chat/Attività, *da aggiungere* | `GET /runs/{id}/events` via SSE, o protocollo equivalente definito col backend | Eventi `message.delta`, `message.completed`, `run.started`, `step.started`, `step.completed`, `step.failed`, `approval.requested`, `run.completed`, `run.failed`; ogni evento con `runId`, `eventId`, sequenza e timestamp. Gestire riconnessione, duplicati e risposta finale. Polling `GET /runs/{id}` come fallback. |
| Architettura `App.tsx`/`api.ts` | `GET /architecture/graph`, `GET /agents` | Grafo `{version,nodes,edges}`, ID stabili, capacità, tipo, stato. Il grafo rappresenta possibilità, non necessariamente il percorso svolto. |
| Architettura/Attività `App.tsx`/`api.ts` | `GET /runs`, `GET /runs/{id}` | Stato del run e passi effettivi `{id,runId,nodeId,parentStepId,status,summary,startedAt,finishedAt}`; selezione run e corrispondenza con nodi. In futuro filtri e paginazione. |
| Attività/Chat `App.tsx`/`api.ts` | `POST /approvals/{id}` con `{decision:"approved"|"rejected"}` | Anteprima comprensibile dell'azione, scadenza, risposta idempotente e nuovo stato. Nessuna esecuzione implicita per apertura pagina. |
| Programma `App.tsx`/`api.ts` | `GET /workspaces`, `GET /workspaces/{id}/files`, `GET /workspaces/{id}/file?path=...` | Aree autorizzate `cora` e `project`, radici visibili, permessi, albero e file con `revision`; filtrare e normalizzare percorsi sul server. |
| Programma `App.tsx`/`api.ts` | `PUT /workspaces/{id}/file` con `{path,content,revision}` | Salvataggio solo dove `WRITE`; controllo revisione/conflitti (`409`), audit e risposta con nuova revisione. |
| Programma, *da aggiungere* | `POST /workspaces/{id}/executions` con comando/target validato; `GET /executions/{id}` + eventi/output | Solo dove `EXECUTE`, su comandi allowlist o sandbox; timeout, cancellazione, stdout/stderr, exit code, limiti e conferma quando prevista. Non accettare shell arbitraria tramite UI. |
| Calendario `App.tsx`/`api.ts` | `GET /calendar/events?from=...&to=...`, `POST /calendar/events`, `PATCH /calendar/events/{id}`, `DELETE /calendar/events/{id}` | Eventi con titolo, inizio, fine, note e fuso. Solo operazioni dell'utente autenticato; nessuna capability agente calendario. |
| File `components/FileManager.tsx`/`api.ts` | `GET /server/files/tree`, `GET /server/files/folders/{id}/children`, `GET /server/storage` | ID opachi, parent, nome, tipo, dimensione, modifica, capacità per elemento, utilizzo disco; navigazione e ricerca con paginazione per grandi directory. Non esporre percorsi assoluti o file fuori dalle radici autorizzate. |
| File `components/FileManager.tsx`/`api.ts` | `POST /files` multipart con folderId, `GET /files/{id}/download`, `DELETE /server/files/{id}`, `POST /server/files/{id}/shares` | Upload nella cartella autorizzata, progresso e limiti, download autenticato, conferma e cestino/versione per eliminazione, condivisione solo se autorizzata. Le risposte devono aggiornare elenco e spazio usato. Distinguere NAS da allegati chat/artefatti Cora. |
| File, *da aggiungere* | `GET /files/{id}/preview`, `GET /files/{id}/processing` | Anteprima sicura per tipi supportati e stato del processo; risultati generati collegati a conversazione e run. |
| Audio/microfono, *fase futura* | Permesso browser + upload audio/trascrizione da definire | Acquisizione con consenso esplicito, stato registrazione, upload, testo, errori e retention. Il pulsante è disabilitato fino al collegamento. |
| Architettura modificabile, *fase futura* | Endpoint separati con versioni, validazione, simulazione e pubblicazione | Bozze del grafo/automazioni, controllo cicli e capability, diff, conferma, audit e rollback. La mappa iniziale è sola lettura. |
| AVVIO completo, *collegato localmente* | `/health` e marker HTML del nuovo frontend | Il launcher `serveria1/AVVIO.cmd` avvia i servizi locali. La configurazione automatica di un server remoto resta da definire. |

### Integrazioni trasversali indispensabili

1. **Autenticazione e sessione:** decidere il modello locale/remoto prima di abilitare dati reali. `api.ts` prevede `credentials: 'include'`; se si usano cookie, servono attributi corretti, protezione CSRF per mutazioni, CORS con origini esplicite e HTTPS per accesso remoto. Non inserire token permanenti in `localStorage` o nel bundle Vite.
2. **Permessi reali:** `Programma` offre Cora e progetti separati, ma il backend deve imporre radici autorizzate, operazioni per workspace e percorso, isolamento da symlink/path traversal, revoche, conferme e audit. Disabilitare pulsanti nella UI è solo una comodità visiva. Gli agenti non ottengono accesso ai file perché la pagina Programma può aprirli.
3. **Sincronizzazione degli stati:** invio chat → `runId` → eventi o polling → risposta e passi → eventuale conferma → risultato/file. Gli stati devono sopravvivere a refresh, più tab, timeout e riconnessione. Errori e operazioni in sospeso devono essere distinti da successi.
4. **Identità degli artefatti:** ogni file generato deve dichiarare `sourceRunId`, `conversationId`, MIME, dimensione e diritti di accesso. Ogni evento attività deve puntare a un run; ogni passo al nodo del grafo con `nodeId` stabile.
5. **Calendario umano:** gli endpoint CRUD sono per l'utente. Qualunque accesso futuro di Cora al calendario richiede una scelta esplicita successiva; la UI attuale non promette tale integrazione.
6. **Contratto evolutivo:** prefisso versione API, schema OpenAPI da FastAPI, tipi TS generati o verificati contro lo schema, codici di errore, limiti e test di contratto. I nomi sopra sono proposti: aggiornare questa matrice e `services/api.ts` quando il backend concorda lo schema.
7. **Configurazione:** host/porta tramite `.env`, nessun percorso locale hardcoded, nessun segreto nelle variabili `VITE_` (finiscono nel client). In produzione il frontend può essere servito dallo stesso origin o tramite reverse proxy; documentare origin, CORS e base path.
8. **Dati e privacy:** cancellazione, retention, limiti degli upload, sanitizzazione delle anteprime e resa sicura di testo/Markdown/codice. Il frontend non deve eseguire contenuti restituiti dagli agenti.


## Direzione del progetto

Il backend resta la fonte dei dati e dei permessi. I prossimi collegamenti si aggiungono uno alla volta, rimuovendo l’avviso corrispondente solo dopo una verifica completa. La console mantiene la struttura modulare e locale di Cora.
