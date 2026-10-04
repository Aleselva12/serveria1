# Cora Lab

Cora è un assistente locale con backend FastAPI, frontend React/Vite, agenti LangGraph e modelli Ollama. Backend e frontend sono mantenuti **nella stessa repository**, in cartelle separate. Questa è la fonte del codice dell'applicazione; la vecchia repository `frontend` è archiviata.

## Avvio sul PC

1. Copiare `.env.example` in `.env` e impostare `CORA_DATABASE_URL`, percorsi autorizzati e configurazione Ollama.
2. Avviare PostgreSQL + pgvector: `docker compose -f docker-compose.database.yml up -d`.
3. Su Windows AVVIO prepara automaticamente `.venv` e le dipendenze principali. Installazione manuale: `python -m pip install -r requirements-core.txt`. Per sola trascrizione CPU aggiungere `requirements-audio-cpu.txt` oppure usare `AVVIO.cmd -ConAudio`. Per diarizzazione aggiungere `requirements-audio.txt` oppure usare `AVVIO.cmd -ConDiarizzazione`; `requirements.txt` installa tutto. Il profilo Docker offline è descritto in `deploy/README.md`.
4. AVVIO verifica PostgreSQL, tenta di avviare il container `cora-postgres` se esiste e chiede nome/password soltanto se manca il proprietario. Per crearlo manualmente o cambiare password, dalla radice della repository e con lo stesso ambiente Python del backend, eseguire `python -m core.auth`. Inserire nome e password, richiesti in modo interattivo. Su Windows con l'ambiente creato da AVVIO: `.\.venv\Scripts\python.exe -m core.auth`. Il comando crea il proprietario o cambia la sua password e revoca le sessioni precedenti. Non mettere la password nel codice o nelle variabili frontend.
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

Per il percorso Debian con Docker Compose, frontend compilato, Ollama esterno,
backup e ripristino consultare [deploy/README.md](deploy/README.md).

`core/runtime.py` ammette un'esecuzione del modello alla volta, con coda FIFO limitata e una sola richiesta attiva per conversazione. Lo streaming mostra sia Supervisor sia specialisti, distinguendo ogni nuova chiamata e sostituendo il testo provvisorio con il risultato salvato. Il nuovo ingresso chat è `POST /api/v1/chat/runs`; `POST /chat` conserva il contratto sincrono per i client precedenti. Il frontend riceve testo e stati attraverso SSE.

Lifecycle: `queued → running → completed / failed / awaiting_approval`. Un annullamento avviato durante il lavoro passa per `cancelling` e termina come `cancelled` o `timed_out`. La mappa degli stati è unica in `core/run_states.py`. Stato, risultato finale, proposte e motivo dell’arresto sono persistenti in `runtime_runs`; le transizioni bloccano la riga e verificano lo stato precedente. Uno stato terminale non può essere riscritto o riaperto. Al riavvio i run incompiuti diventano `interrupted`; non vengono rieseguiti automaticamente. Le tracce tecniche sono diagnostiche e non determinano il lifecycle.

Annullare una delega marca la radice e tutti i discendenti attivi: si arresta l’intera catena. La cancellazione è **cooperativa**: controlli prima dei nodi/tool e durante i token del modello, timeout HTTP verso Ollama, timeout delle query PostgreSQL. Un'operazione bloccante già partita può terminare prima che la cancellazione venga osservata. Il runtime mantiene occupato il posto fino al ritorno; nessun rollback implicito di effetti già avvenuti e nessun rifiuto automatico delle proposte già salvate. Il timeout del run include coda, contesto e salvataggi. Il modello ha un timeout di lettura distinto.

`core/operation_journal.py` registra una riga prima dell’invocazione effettiva, con attore, contratto/revisione, parametri normalizzati, run e proposta collegati. L’avvio verifica sotto lock che il run radice sia ancora eseguibile. Il risultato è registrato separatamente dal run: un run annullato può contenere una scrittura riuscita, e una perdita del salvataggio finale del run non cancella un successo già registrato del tool.

Le operazioni terminano come `succeeded`, `pending`, `failed` o `uncertain`. Un errore dopo l’avvio di una scrittura/delega viene classificato conservativamente `uncertain`, perché non prova l’assenza di effetti. Il ragionamento dell’agente si interrompe su questo esito. Le letture/calcoli interrotti sono `failed`. Il recupero di avvii privi di risultato segue la stessa distinzione; le proposte generiche rimaste `executing` diventano `uncertain`. Nessun run, lettura o scrittura viene ripreso automaticamente.

Un indice univoco impedisce l’avvio di una scrittura/delega con lo stesso ID capability e lo stesso input normalizzato quando ne esiste una in corso o dall’esito incerto non verificato. Questo protegge i tentativi identici, non è deduplicazione semantica di payload diversi né una garanzia di exactly-once per servizi esterni. In Attività si registrano autore, nota ed esito della verifica (`effect_verified` / `no_effect_verified`); la riga conserva lo stato originale e la verifica non esegue azioni. Solo una nuova richiesta esplicita può produrre un nuovo tentativo. I tool di dominio potranno in seguito distinguere errori senza effetti da effetti parziali con evidenze specifiche.

Se non può registrare l’avvio, il runtime non esegue il tool. Se perde il registro degli esiti o delle transizioni, interrompe la catena, segnala lo stato persistente non confermato e non ammette nuovi run fino al riavvio. Il database deve essere configurato anche per l’esecuzione diretta delle capability. `Runtime(persistent=False)` è riservato ai test unitari del coordinatore; non è un fallback del programma. Un errore di scrittura delle tracce tecniche viene segnalato in `/runtime` e in Attività e non trasforma un risultato canonico riuscito in fallimento.

Le API `/api/v1/runtime/runs` e `/runtime/runs/{id}` leggono lo stato persistente anche dopo l’uscita del run dalla cache. Il canale eventi di un run archiviato restituisce il risultato finale salvato, senza ricostruire o ripetere i token precedenti. `/runtime/operations` mostra il registro delle invocazioni; `/runtime/operations/{id}/review` registra una verifica del proprietario. Parametri e risultati di questo registro sono dati applicativi privati in PostgreSQL, distinti dalle tracce tecniche senza contenuti.

L’esecuzione e il recupero di avvio richiedono **un solo processo backend/worker** per questo database, come il comando di avvio attuale. Non avviare repliche che condividono questi run: il coordinamento distribuito e il takeover con lease non sono implementati. Il registro degli effetti è nuovo: i run precedenti non hanno una ricostruzione retroattiva delle singole invocazioni.

Il prompt di turno e il contesto permanente sono riutilizzati; i tool deterministici e le deleghe con risultato finale possono terminare senza un secondo passaggio del Supervisor. Le letture sicure possono essere eseguite in parallelo, le scritture vengono serializzate. Trascrizioni derivate ed episodi sono aggiornati fuori dal percorso di risposta.

La profilazione conserva durate di coda, preparazione del contesto, modelli, tool e salvataggi; registra i conteggi e le durate restituiti da Ollama quando disponibili. I log tecnici non registrano prompt, parametri tool o risposte. Le metriche finali sono nelle tracce persistenti e consultabili in Attività come tabella leggibile: coda, primo testo, modelli, tool, caricamento e token/s quando disponibili. I dati tecnici completi restano consultabili. Le durate dei nodi nidificati possono sovrapporsi: non sommarle per calcolare il tempo totale.

I messaggi sono salvati immediatamente senza attendere gli embedding. `core/background_embeddings.py` prepara le sintesi e indicizza la coda persistente dopo almeno 15 secondi senza lavoro in primo piano; usa lo stesso posto del modello. Gli embedding sono richiesti in piccoli batch (due messaggi predefiniti). Se arriva un run, una sintesi cede il posto al termine della chiamata al modello corrente e conserva i batch già conclusi. Un indice fallito non perde il testo, viene marcato con il modello e non viene ritentato continuamente. Per ritentare deliberatamente una mancata indicizzazione, azzerare `embedding_model` dei soli messaggi interessati ancora privi di embedding. La ricerca memoria salta gli embedding se l’archivio è vuoto, riusa per 60 secondi le query identiche e ha un timeout predefinito di cinque secondi, con fallback lessicale. Esclude risultati sotto una soglia configurabile. Anche la scrittura delle memorie salva subito il testo: gli embedding vengono preparati nel worker inattivo e applicati solo alla versione ancora corrente. Un embedding fallito resta marcato; per ritentare deliberatamente azzerare embedding_model delle sole memorie interessate prive di embedding.

Le memorie semantiche hanno `assertion` (affermazione utente, osservazione, deduzione/ipotesi, non classificata), confidenza facoltativa dichiarata dall'autore, scadenza, provenienza e versione. Il tipo `fact` è una categoria, non una certificazione di verità. Cora può annotare deduzioni utili come ipotesi; non viene aggiunto un estrattore automatico delle conversazioni. Il recupero automatico resta nel Supervisor (massimo sei candidati e 2.048 token stimati di dati); le deduzioni non vengono promosse a istruzioni. I riferimenti ID/versione dei candidati preparati sono emessi in `memory.selected`, mentre `context.selected` indica se il blocco entra effettivamente nella chiamata. Gli specialisti ricevono la richiesta delegata e il contesto permanente comune; non leggono automaticamente tutto l'archivio. Se il recupero fallisce, il turno lo registra e il modello riceve un avviso di memoria non consultata.

Ogni modifica conserva il contenuto precedente in `memory_versions`. Creare richiede `expected_version=0`; aggiornare richiede ID (`expected_memory_id`) e versione letti, con HTTP 409 per una versione obsoleta. Anche con permessi automatici, una correzione o eliminazione da parte di Cora di una memoria dell'utente (o di provenienza precedente sconosciuta) richiede approvazione generica dell’identità e versione esatte. Una tua modifica successiva rende la proposta inutilizzabile. La pagina Gestione Memoria permette modifica, confronto delle versioni, classificazione, confidenza e scadenza; può mostrare anche memorie scadute, escluse dal recupero degli agenti. Eliminare una memoria elimina anche il suo storico e le fonti, coerentemente con la richiesta di dimenticarla; gli archivi di run/chat restano separati. La classificazione degli errori di scrittura nel journal resta conservativa: una proposta obsoleta può richiedere una verifica in Attività, ma non cambia il contenuto.

Il contesto permanente è letto dal database una volta per run radice e condiviso con tutte le deleghe. Un errore di lettura interrompe la preparazione, invece di togliere silenziosamente le tue istruzioni. Gli aggiornamenti dalle Impostazioni richiedono la versione letta e conservano uno storico SQL (`system_context_versions`); dopo un conflitto la bozza resta intatta e puoi caricare esplicitamente la versione salvata. Le memorie precedenti vengono migrate a versione 1 e restano **non classificate**; non si ricostruisce uno storico che non è stato registrato. I contratti modificati dei tool invalidano le vecchie proposte generiche: crea proposte nuove dopo l'aggiornamento.

`core/context_budget.py` conserva identità e istruzioni, una sintesi separata degli scambi vecchi e messaggi recenti. La sintesi viene riutilizzata e aggiornata in PostgreSQL, non trasformata in memoria semantica. Un riferimento al messaggio già coperto permette di leggere soltanto il seguito. Le sintesi vengono preparate durante l’inattività tramite job persistenti; il turno prepara gli aggiornamenti mancanti quando necessario. La prima sintesi di una chat lunga importata può ancora richiedere più chiamate. Ogni agente seleziona turni utente completi prima del modello: chiamate parallele e risultati tool sono indivisibili. La richiesta corrente e tutti i suoi scambi sono obbligatori; non si scarta la richiesta per far entrare un risultato. Sintesi e memorie recuperate sono dati facoltativi, separati dalle istruzioni. Le query della cronologia sono paginate (64 messaggi per lettura). Il cursore della sintesi avanza solo dopo un messaggio interamente elaborato; un arresto durante un messaggio molto grande ricalcola quel messaggio al prossimo tentativo. Il conteggio preventivo è una stima conservativa UTF-8, non il tokenizer esatto del modello: i conteggi reali di Ollama servono alla taratura. Un turno corrente troppo grande o con scambi tool incompleti viene rifiutato esplicitamente; nessuna troncatura silenziosa. La selezione pubblica context.selected con budget stimato, spazio tool, dati facoltativi inclusi e turni esclusi; le metriche restano nel risultato persistente del run. Gli schemi dei tool effettivamente assegnati e l’output hanno spazio riservato; il contesto predefinito è 16.384 token, configurabile. `num_ctx` e `num_predict` sono impostati esplicitamente.

PostgreSQL usa un pool per processo, con connessioni riutilizzate, registrazione pgvector una volta per connessione, attesa limitata, rollback delle transazioni fallite e chiusura nel lifecycle FastAPI. Eseguire **un solo processo Uvicorn**: coda, bus, rate limit e stati vivi sono locali al processo.

## Permessi e approvazioni

Il Permission Engine nega le azioni sconosciute e distingue `auto`, `confirm`, `blocked`. I tool eseguibili sono registrati con attore fisso; l'LLM non può scegliere un'identità o fornire un'approvazione. `GET /api/v1/runtime/registry` unisce componenti, tool effettivi, schema parametri, azioni e regole. Il catalogo grafico mantiene anche API e predisposizioni, distinguendole dalle capability degli agenti.

Nella pagina Attività si possono consultare e modificare le policy per azione, fermare un run e gestire le proposte. Le capability bloccate alla base perché prive di un percorso verificato restano bloccate. Le policy effettive sono conservate in PostgreSQL.

Le proposte generiche contengono attore, azione, tool e parametri esatti; scadono dopo 24 ore. La risoluzione verifica anche la revisione del tool, ricontrolla i permessi e reclama la proposta una sola volta prima dell'effetto. Uno stato `executing` lasciato da un arresto richiede verifica manuale dell'esito: non viene ripetuto. Errori strutturati del tool non vengono segnati come successo. L'esito è disponibile in Attività. L'approvazione esegue soltanto l'azione mostrata: non fa continuare automaticamente il ragionamento di Cora.

Le richieste del precedente prototipo non legate a un tool restano nel database per evitare perdita di dati; non vengono convertite in autorizzazioni eseguibili. Il servizio operativo è unico.

Il calendario conserva il proprio flusso transazionale e il controllo di versione; le sue proposte sono visibili anche nel pannello comune. Con policy `auto` i tool calendario possono applicare l'azione direttamente, con `confirm` producono proposte, con `blocked` negano l'azione. Il salvataggio manuale dell'utente non passa dalla policy di un agente.

## Contratti ed esecuzione delle capability

`core/capability_contracts.py` definisce il contratto eseguibile: ID stabile `attore.capability`, versione intera, schemi input/output, permessi obbligatori e condizionali, effetto (`read`, `compute`, `write`, `delegate`), ripetibilità e percorso di approvazione. Le dichiarazioni sono esplicite nei decoratori `agent_tool`; non vengono dedotte dal codice con AST. `bind_capabilities` registra gli oggetti effettivamente collegati ai grafi e verifica l’attore.

Tutti gli adapter degli agenti e le conferme generiche chiamano `execute_capability`: valida input stretti, rifiuta campi sconosciuti, normalizza i valori iniziali, controlla i permessi obbligatori prima degli effetti, esegue il tool e valida il risultato. Il tool può controllare solo azioni dichiarate per il proprio attore; non può concedersi conferma con `user_approved=True`. I permessi condizionali vanno controllati nel ramo che li richiede, prima del relativo effetto. Questo confine disciplina codice applicativo fidato; non è una sandbox per Python ostile.

Il risultato comune contiene `capability_id`, `contract_version`, `status` (`ok`, `pending`, `error`), `value`, descrittore di errore, ID di approvazione e ID dell’operazione. Gli adapter LangChain preservano il risultato nativo per compatibilità con i prompt esistenti. Gli output di dominio sono ancora stringhe/dizionari/liste con lo schema del tipo dichiarato: i singoli payload di dominio non sono tutti modellati campo per campo. Errori strutturati vengono riconosciuti; un risultato `pending` deve avere un ID di proposta. Gli errori ordinari degli adapter diventano messaggi di errore nei grafi; cancellazione, perdita della persistenza ed effetti incerti interrompono la catena.

Le nuove proposte generiche fissano ID, versione, digest del contratto, revisione dell’implementazione e input normalizzato. La revisione comprende il modulo del tool e `core/governance.py`, non tutte le dipendenze transitive o la configurazione esterna. Una modifica delle dipendenze che cambia il significato dell’azione richiede anche una modifica esplicita del contratto/versione. Proposte precedenti senza riferimenti al contratto restano consultabili e rifiutabili, ma richiedono una nuova proposta per essere eseguite. Il calendario mantiene il proprio protocollo transazionale.

`GET /api/v1/runtime/registry` espone il registry v2. Il catalogo Tools usa gli stessi contratti e collegamenti; API HTTP e predisposizioni sono voci separate. Il diagramma resta illustrativo e le automazioni restano bozze. Non è introdotto un endpoint pubblico di esecuzione manuale. `retry="safe"` dichiara la ripetibilità di letture/calcoli: non attiva retry automatici; scritture e deleghe usano `never`.

Per aggiungere una capability: scegliere un ID stabile, dichiarare azioni/effetto/ripetibilità, annotare input e output, registrare le regole di permesso e collegare l’adapter al grafo con `bind_capabilities`. Una modifica incompatibile di input, output, permessi o significato dell’effetto richiede l’incremento della versione; il digest rileva comunque ogni modifica del contratto per le conferme pendenti. Evitare di rinominare un ID esistente per un semplice spostamento di modulo.

## Protocollo componenti e bus

`core/protocol.py` definisce envelope v1 per richieste/eventi: ID, sorgente, destinazione/capability per richieste, run, thread, correlazione, timestamp/deadline e payload. Il bus di `core/event_bus.py` è in-process, con buffer limitato, sequenza e replay; lifecycle, tool e streaming lo usano. Non aggiunge Redis o round-trip di rete ai turni del modello.

Il bus live non è una coda distribuita durevole. Il cursore SSE è `process_id:sequence`: dopo riavvio, cursore invalido o perdita del buffer, lo streaming invia uno snapshot `resync`, senza duplicare i delta precedenti. Le deleghe ai quattro agenti passano dal dispatcher tipizzato `core/component_bus.py`; gli eventi distinguono radice (`run_id`), run del componente, padre, span e operazione. I nodi interni continuano a usare il contratto nativo del framework.

### Eventi critici e diagnostica

`domain_events` conserva fatti di lifecycle, richiesta di arresto e registro operazioni nella **stessa transazione** dello stato canonico. Un errore annulla entrambi. Un contatore transazionale ordina i commit; il cursore persistente è distinto dal cursore live. `/api/v1/runtime/domain-events` permette letture paginate, ma non esegue comandi, subscriber o retry di azioni. Non viene ricostruito lo storico precedente alla migrazione e questi fatti non scadono con la diagnostica.

`diagnostic_events` raccoglie solo metadati consentiti: classificazioni, ID, tempi, conteggi e riferimenti. Prompt, messaggi, argomenti, risultati tool e testo delle eccezioni non vengono archiviati in questo percorso; i delta chat restano transitori. Una coda limitata e un writer asincrono separano le scritture diagnostiche dai turni. Overflow, indisponibilità del database o arresto del processo possono perdere dettagli: `/runtime` e Attività espongono salute, attese ed eventi scartati. I contatori sono locali al processo e ripartono al riavvio, non costituiscono un audit permanente delle perdite.

La conservazione diagnostica predefinita è **30 giorni**, configurabile con `CORA_DIAGNOSTIC_RETENTION_DAYS` (1–3650); la pulizia è incrementale. `/runtime/diagnostics` usa pagine per timestamp/ID; un cursore scaduto richiede una nuova lettura (409). La vista delle esecuzioni legge sempre il lifecycle SQL, carica i dettagli soltanto per il run selezionato e dichiara il campione diagnostico incompleto. Tempi e primo token sono misurati per invocazione; durate sovrapposte non vanno sommate.

Non si scrivono più nuovi eventi in `agent_events` o `cora.jsonl`. L'export tecnico JSONL, solo metadati, è opzionale (`CORA_DIAGNOSTIC_JSONL_EXPORT=true`) e non sostituisce SQL. I file e le righe storiche preesistenti non vengono importati, cancellati o sanitizzati retroattivamente. `/runtime/event-contracts` espone il contratto. La modifica del confine `governance.py` richiede di rigenerare le proposte generiche pendenti: le vecchie revisioni non vengono eseguite automaticamente.

## Dati, file e interfaccia

PostgreSQL + pgvector conserva conversazioni/messaggi, memorie/relazioni/fonti, episodi, contesto permanente, working memory, calendario/storico/proposte, utenti/sessioni, policy e approvazioni. Le trascrizioni Markdown sono copie derivate delle chat. Il lifecycle è conservato in `runtime_runs`, con run delle deleghe collegati al run padre; `domain_events` conserva i fatti critici e `diagnostic_events` i campioni tecnici. Il database è necessario per le operazioni persistenti: non esiste un fallback SQLite.

Il contesto permanente in modifica non viene sovrascritto dai controlli periodici, dalle riconnessioni o da salvataggi precedenti ancora in volo. Cataloghi e permessi vengono caricati all’apertura (i permessi anche dopo modifica), mentre gli stati restano aggiornati periodicamente; il polling si sospende nella scheda nascosta.

La UI comprende Home con misure reali disponibili, chat con cronologia persistente e streaming, File server/Libreria IA, architettura generale e tools con editor grafico delle bozze, Programma predisposto, calendario mese/giorno, Attività, Impostazioni e Gestione Memoria. In assenza di backend si può visualizzare l'interfaccia offline senza fingere che le operazioni siano riuscite.

I file server sono gestiti sotto risorse autorizzate da `CORA_FILE_ROOTS`, con upload, download, cartelle, copia/spostamento/rinomina, cestino e ripristino. La Libreria IA opera su copie in `CORA_KNOWLEDGE_ROOT`; gli upload conservano un originale distinto. Protezioni di percorso, link, limiti upload, conflitti e sola lettura restano attive. I file caricati sul server non diventano automaticamente documenti dell'IA. Non puntare cartelle scrivibili agli archivi interni di Immich/Nextcloud.

## Verifica

- Backend: `python -m unittest discover -s tests -v` (installare anche `httpx`).
- Test transazionali: usare **esclusivamente un database sacrificabile** e impostare `CORA_CALENDAR_TEST_DATABASE_URL` e `CORA_RUNTIME_TEST_DATABASE_URL`; per i test runtime impostare anche `CORA_DATABASE_URL` allo stesso database. Questi test cancellano dati di prova.
- Import e copertura: `python smoke_check.py`.
- Frontend, nella sua cartella: `npm test` e `npm run build`.

Non ancora implementati: orchestratore autonomo, agente programmatore e automodifica, esecutore/pianificazione delle bozze grafiche, server multiutente, bus distribuito, arresto forzato sicuro di qualsiasi tool, ripresa automatica dei run interrotti. La latenza sul PC reale e il comportamento del modello locale vanno misurati con la nuova profilazione; i test non equivalgono a un benchmark di Ollama o Whisper sul server finale.
