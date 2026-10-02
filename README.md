# Cora Lab

Cora è un assistente locale con backend FastAPI, frontend React/Vite, agenti LangGraph e modelli Ollama. Backend e frontend sono mantenuti **nella stessa repository**, in cartelle separate. Questa è la fonte del codice dell'applicazione; la vecchia repository `frontend` è archiviata.

## Avvio sul PC

1. Copiare `.env.example` in `.env` e impostare `CORA_DATABASE_URL`, percorsi autorizzati e configurazione Ollama.
2. Avviare PostgreSQL + pgvector: `docker compose -f docker-compose.database.yml up -d`.
3. Installare le dipendenze nell'ambiente Python: `python -m pip install -r requirements.txt`.
4. **Prima del primo accesso**, dalla radice della repository e con lo stesso ambiente Python del backend, eseguire `python -m core.auth`. Inserire nome e password, richiesti in modo interattivo. Su Windows con l'ambiente creato da AVVIO: `.\.venv\Scripts\python.exe -m core.auth`. Il comando crea il proprietario o cambia la sua password e revoca le sessioni precedenti. Non mettere la password nel codice o nelle variabili frontend.
5. Avviare `AVVIO.cmd` su Windows oppure `uvicorn api:app --host 127.0.0.1 --port 8000` e, in `frontend`, `npm ci` seguito da `npm run dev`.
6. Aprire `http://127.0.0.1:5173` e accedere. La sessione dura sette giorni; nelle Impostazioni sono disponibili logout e revoca di tutti i dispositivi.

Il launcher verifica `/auth/status`, pubblico e privo di dati del server. Tutte le API operative, `/health`, documentazione OpenAPI e download richiedono la sessione. Il browser usa un cookie HttpOnly, SameSite Strict; le scritture richiedono anche `X-Cora-Client: ui` e, quando presente, un'Origin autorizzata da `CORA_UI_ORIGINS`. I token File/Calendario precedenti non sostituiscono il login globale. Le vecchie verifiche restano nei router per i test e gli utilizzi isolati; l'app autenticata riusa l'identità del proprietario.

Per accesso remoto mantenere backend, PostgreSQL e Ollama nella rete privata. Servire UI e API sullo stesso sito tramite proxy e Tailscale, configurare l'origine reale in `CORA_UI_ORIGINS`. Con HTTPS impostare `CORA_COOKIE_SECURE=true`; il valore false serve per HTTP locale. È implementato un unico proprietario: la struttura account/sessioni non costituisce ancora isolamento dei dati fra più utenti.

## Agenti e capacità

Il Supervisor risponde o delega a quattro agenti distinti:

| Agente | Capacità implementate |
| --- | --- |
| Supervisor | Calcolatrice, monitoraggio, lettura file autorizzati, registro componenti, memoria persistente e deleghe. |
| Structure | Planning, evaluation, control e management; scrive soltanto nel proprio workspace. |
| Local Research | Documenti locali, ricerca lessicale, lettura Word/PDF/testo, nuovi Word e append non distruttivo. Non cerca sul web. |
| Audio | Trascrizione locale faster-whisper, timestamp, diarizzazione locale opzionale, riassunti e salvataggio trascrizioni. |
| Email & Quotes | Ricerca e lettura Gmail, riepiloghi, bozze Gmail e preventivi PDF da dati strutturati. Invio email bloccato. |

Le azioni calendario sono tool assegnati agli agenti autorizzati, senza un agente calendario dedicato. PostgreSQL è la fonte degli eventi, con versioni, storico, eliminazione recuperabile e proposte.

Modello predefinito: `gpt-oss:20b`, endpoint `http://localhost:11435`. Le variabili `CORA_MODEL_SUPERVISOR/STRUCTURE/RESEARCH/AUDIO/EMAIL` consentono scelte per ruolo. La configurazione effettiva si trova in `core/models.py`; le richieste dei modelli non usano proxy di ambiente.

## Runtime e prestazioni

`core/runtime.py` ammette un'esecuzione del modello alla volta, con coda FIFO limitata e una sola richiesta attiva per conversazione. Il nuovo ingresso chat è `POST /api/v1/chat/runs`; `POST /chat` conserva il contratto sincrono per i client precedenti. Il frontend riceve testo e stati attraverso SSE.

Lifecycle: `queued → running → completed / failed / awaiting_approval`. Un annullamento avviato durante il lavoro passa per `cancelling` e termina come `cancelled` o `timed_out`. Al riavvio le tracce incompiute diventano `interrupted`; non vengono rieseguite automaticamente.

La cancellazione è **cooperativa**: controlli prima dei nodi/tool e durante i token del modello, timeout HTTP verso Ollama, timeout delle query PostgreSQL. Un'operazione bloccante già partita può terminare prima che la cancellazione venga osservata. Il runtime mantiene occupato il posto fino al ritorno; nessun rollback implicito di effetti già avvenuti. Il timeout del run include coda, contesto e salvataggi. Il modello ha un timeout di lettura distinto.

Il prompt di turno e il contesto permanente sono riutilizzati; i tool deterministici e le deleghe con risultato finale possono terminare senza un secondo passaggio del Supervisor. Le letture sicure possono essere eseguite in parallelo, le scritture vengono serializzate. Trascrizioni derivate ed episodi sono aggiornati fuori dal percorso di risposta.

La profilazione conserva durate di coda, preparazione del contesto, modelli, tool e salvataggi; registra i conteggi e le durate restituiti da Ollama quando disponibili. I log tecnici non registrano prompt, parametri tool o risposte. Le metriche finali sono nelle tracce persistenti e consultabili in Attività. Le durate dei nodi nidificati possono sovrapporsi: non sommarle per calcolare il tempo totale.

I messaggi sono salvati immediatamente senza attendere gli embedding. `core/background_embeddings.py` indicizza la coda persistente quando non ci sono run in attesa; usa lo stesso posto del modello. Un indice fallito non perde il testo, viene marcato con il modello e non viene ritentato continuamente. Per ritentare deliberatamente una mancata indicizzazione, azzerare `embedding_model` dei soli messaggi interessati ancora privi di embedding. Memorie e ricerca semantica mantengono i loro embedding sincroni.

`core/context_budget.py` conserva identità e istruzioni, una sintesi separata degli scambi vecchi e messaggi recenti. La sintesi viene riutilizzata e aggiornata in PostgreSQL, non trasformata in memoria semantica. Ogni agente limita anche la cronologia dei propri turni/tool prima del modello. Il conteggio preventivo è una stima conservativa UTF-8, non il tokenizer esatto del modello: i conteggi reali di Ollama servono alla taratura. Un singolo messaggio o risultato troppo grande viene rifiutato. Gli schemi dei tool effettivamente assegnati e l’output hanno spazio riservato; il contesto predefinito è 16.384 token, configurabile. `num_ctx` e `num_predict` sono impostati esplicitamente.

PostgreSQL usa un pool per processo, con connessioni riutilizzate, registrazione pgvector una volta per connessione, attesa limitata, rollback delle transazioni fallite e chiusura nel lifecycle FastAPI. Eseguire **un solo processo Uvicorn**: coda, bus, rate limit e stati vivi sono locali al processo.

## Permessi e approvazioni

Il Permission Engine nega le azioni sconosciute e distingue `auto`, `confirm`, `blocked`. I tool eseguibili sono registrati con attore fisso; l'LLM non può scegliere un'identità o fornire un'approvazione. `GET /api/v1/runtime/registry` unisce componenti, tool effettivi, schema parametri, azioni e regole. Il catalogo grafico mantiene anche API e predisposizioni, distinguendole dalle capability degli agenti.

Nella pagina Attività si possono consultare e modificare le policy per azione, fermare un run e gestire le proposte. Le capability bloccate alla base perché prive di un percorso verificato restano bloccate. Le policy effettive sono conservate in PostgreSQL.

Le proposte generiche contengono attore, azione, tool e parametri esatti; scadono dopo 24 ore. La risoluzione verifica anche la revisione del tool, ricontrolla i permessi e reclama la proposta una sola volta prima dell'effetto. Uno stato `executing` lasciato da un arresto richiede verifica manuale dell'esito: non viene ripetuto. Errori strutturati del tool non vengono segnati come successo. L'esito è disponibile in Attività. L'approvazione esegue soltanto l'azione mostrata: non fa continuare automaticamente il ragionamento di Cora.

Le richieste del precedente prototipo non legate a un tool restano nel database per evitare perdita di dati; non vengono convertite in autorizzazioni eseguibili. Il servizio operativo è unico.

Il calendario conserva il proprio flusso transazionale e il controllo di versione; le sue proposte sono visibili anche nel pannello comune. Con policy `auto` i tool calendario possono applicare l'azione direttamente, con `confirm` producono proposte, con `blocked` negano l'azione. Il salvataggio manuale dell'utente non passa dalla policy di un agente.

## Protocollo componenti e bus

`core/protocol.py` definisce envelope v1 per richieste/eventi: ID, sorgente, destinazione/capability per richieste, run, thread, correlazione, timestamp/deadline e payload. Il bus di `core/event_bus.py` è in-process, con buffer limitato, sequenza e replay; lifecycle, tool e streaming lo usano. Non aggiunge Redis o round-trip di rete ai turni del modello.

È una prima infrastruttura interna, non una coda distribuita durevole: dopo riavvio si usano le tracce e il database, non il replay del bus. Le deleghe ai quattro agenti passano dal dispatcher tipizzato `core/component_bus.py`, che collega richiesta, stato e correlazione agli input LangGraph. I nodi interni continuano a usare il contratto nativo del framework.

## Dati, file e interfaccia

PostgreSQL + pgvector conserva conversazioni/messaggi, memorie/relazioni/fonti, episodi, contesto permanente, working memory, calendario/storico/proposte, utenti/sessioni, policy e approvazioni. Le trascrizioni Markdown sono copie derivate delle chat. Il lifecycle è conservato in `runtime_runs`, con run delle deleghe collegati al run padre. I log JSONL e le tracce tecniche restano distinti; gli eventi applicativi sono inoltre salvati nella tabella `agent_events`. Il database è necessario per le operazioni persistenti: non esiste un fallback SQLite.

La UI comprende Home con misure reali disponibili, chat con cronologia persistente e streaming, File server/Libreria IA, architettura generale e tools con editor grafico delle bozze, Programma predisposto, calendario mese/giorno, Attività, Impostazioni e Gestione Memoria. In assenza di backend si può visualizzare l'interfaccia offline senza fingere che le operazioni siano riuscite.

I file server sono gestiti sotto risorse autorizzate da `CORA_FILE_ROOTS`, con upload, download, cartelle, copia/spostamento/rinomina, cestino e ripristino. La Libreria IA opera su copie in `CORA_KNOWLEDGE_ROOT`; gli upload conservano un originale distinto. Protezioni di percorso, link, limiti upload, conflitti e sola lettura restano attive. I file caricati sul server non diventano automaticamente documenti dell'IA. Non puntare cartelle scrivibili agli archivi interni di Immich/Nextcloud.

## Verifica

- Backend: `python -m unittest discover -s tests -v` (installare anche `httpx`).
- Test transazionali: usare **esclusivamente un database sacrificabile** e impostare `CORA_CALENDAR_TEST_DATABASE_URL` e `CORA_RUNTIME_TEST_DATABASE_URL`; per i test runtime impostare anche `CORA_DATABASE_URL` allo stesso database. Questi test cancellano dati di prova.
- Import e copertura: `python smoke_check.py`.
- Frontend, nella sua cartella: `npm test` e `npm run build`.

Non ancora implementati: orchestratore autonomo, agente programmatore e automodifica, esecutore/pianificazione delle bozze grafiche, server multiutente, bus distribuito, arresto forzato sicuro di qualsiasi tool, ripresa automatica dei run interrotti. La latenza sul PC reale e il comportamento del modello locale vanno misurati con la nuova profilazione; i test non equivalgono a un benchmark di Ollama o Whisper sul server finale.
