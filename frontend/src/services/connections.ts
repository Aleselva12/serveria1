/** Collegamenti ancora incompleti. Le funzioni già operative non appartengono al backlog. */
export const missingConnections = {
  files: {
    label: "Sincronizzazione delle copie IA",
    detail: "Anteprime, ricerca nelle sottocartelle, link privati revocabili e upload riprendibili sono collegati. La sincronizzazione bidirezionale fra originali e copie IA resta un lavoro futuro.",
    endpoints: "Contratto di sincronizzazione e gestione conflitti da definire",
  },
  agentFileTools: {
    label: "Accesso File Server e gestione avanzata Libreria",
    detail: "Restano da definire accesso agentico al File Server, importazione di originali, gestione cartelle e ripristino agentico. Le funzioni di lettura, copia, modifica e cestino della Libreria sono elencate tra quelle disponibili.",
    endpoints: "Contratti tool, radici autorizzate e policy per azione da implementare",
  },
  graphEdit: {
    label: "Esecuzione delle automazioni grafiche",
    detail: "La mappa agentica è consultabile e Tools permette di modificare bozze grafiche. Mancano esecuzione e pianificazione delle bozze e modifica operativa dell’architettura.",
    endpoints: "API di esecuzione/pianificazione e modifica dell’architettura da definire",
  },
} as const;
export type ConnectionKey = keyof typeof missingConnections;

/** Stato delle funzionalità nel codice; distinto dal collaudo sul server. */
export const homeRoadmap = {
  updatedAt: "16/10/2026",
  serverEvidence: [
    { label: "Inferenza Ollama sul server · 16 ottobre", detail: "Verificato qwen3:8b su Intel Core i3-2100 (2 core/4 thread), solo CPU. Docker non impone limiti espliciti di quota CPU, cpuset o memoria; llama.cpp riporta threadpool n_threads=2. Thinking attivo: 31 min 7,76 s per un saluto; disattivato: 23,16 s. Il run Programmatore dc904feb ha impiegato 41 min 54 s, quasi interamente nella chiamata modello. Questi sono campioni reali, non benchmark generalizzabili." },
    { label: "Metriche del modello senza thinking", detail: "Test qwen3:8b --think=false --verbose su 29 token prompt e 88 token generati: 61,45 s totali, 11,33 s prefill (2,30 token/s), 50,12 s generazione (1,76 token/s), 1,04 s caricamento. La CPU è il principale vincolo osservato; la causa precisa della durata eccezionale con thinking richiede conteggio dei token e ulteriore diagnostica." },
    { label: "Accesso dal telefono", detail: "Accesso a Cora tramite Tailscale riscontrato nella sessione di installazione." },
    { label: "Servizi e percorsi del server", detail: "Inventario dell’11 ottobre: API, web e database sani; storage accessibile, bridge raggiungibile e workspace allineati. Le metriche sotto mostrano lo stato corrente." },
    { label: "Servizi di aggiornamento", detail: "Bridge host e pulsante installati e avviati; lettura della repository GitHub verificata. Aggiornamento riuscito riferito dal proprietario; restano confronto di commit/immagini e prova di recupero." },
  ],
  available: [
    { label: "Accesso e configurazione allineati", detail: "Link condivisi attraverso il login, tentativi distinti per client dal proxy fidato, endpoint Ollama unico e messaggi separati per errori di salvataggio. Richiedono ricostruzione API/web e collaudo sul server." },
    { label: "Copie e modifiche controllate nella Libreria IA", detail: "Copie senza sovrascrittura; modifiche testuali e aggiunte Word approvate in Attività e legate alla versione letta. Cestino solo dopo conferma, senza eliminazione definitiva. Versione precedente conservata nel cestino prima della modifica." },

    { label: "Diagnostica Ollama riservata", detail: "Le tracce mostrano categorie di errore riconosciute: timeout, connessione, modello non trovato, memoria, compatibilità tool e risposta del servizio. Nessun dettaglio grezzo delle eccezioni viene conservato come descrizione diagnostica." },
    { label: "Consultazione agentica Libreria IA", detail: "Tre tool di sola lettura disponibili durante le richieste automatiche, ricerca lessicale per nome e contenuto, percorsi delle fonti e pannello attività in chat. La selezione manuale dei tool prevale. Nessuna ricerca in background." },
    { label: "Chat e memoria persistenti", detail: "Cronologia, streaming, gestione e versioni della memoria; contesto del proprietario consultato selettivamente." },
    { label: "Accesso, permessi e approvazioni", detail: "Login del proprietario, policy delle capability e proposte consultabili in Attività." },
    { label: "Runtime e diagnostica", detail: "Coda, stati persistenti, cancellazione cooperativa, registro operazioni, bus eventi e profilazione." },
    { label: "File, calendario e Tools", detail: "File server e Libreria IA con anteprime, ricerca ricorsiva, condivisioni private e upload riprendibili; calendario e bozze delle automazioni." },
    { label: "Programmatore", detail: "Copilot, workspace isolati, 21 strumenti, skill, registro componenti, consegne ZIP e verifiche Python/contratti/TypeScript/build frontend. Preparazione, pubblicazione, applicazione e rollback delle release seguono i controlli previsti; nessuna attivazione autonoma." },
    { label: "Allegati chat, selezione tool e Audio", detail: "Documenti allegati alle richieste, tool automatici o selezionati manualmente per il singolo invio e pagina Audio per registrazioni salvate, trascrizione locale, correzioni ed esportazione." },
  ],
  next: [
    { id: "LIB-01", state: "Da collaudare", label: "Collaudare Libreria IA con Ollama", detail: "Verificare scelta autonoma dei tool, permessi, fonti e streaming con un documento di prova sul server. Registrare il risultato in Attività; i test simulati non certificano il modello." },
    { id: "PRG-01", state: "Parziale", label: "Collaudare il Programmatore sul server", detail: "Check Docker completati sul server: isolamento Python, riconoscimento dei test falliti, TypeScript e build frontend. Run dc904feb completed in 41 min 54 s per un saluto, senza verifica del workspace; diagnostica conferma tempo quasi interamente nel modello Ollama. Non è una prova di modifica del codice. Restano creazione di un file, test reali e verifica dalla pagina. Pubblicazione GitHub ancora da configurare: chiave server in sola lettura." },
    { id: "PERF-01", state: "Parziale", label: "Misurare e ottimizzare la latenza", detail: "Riscontri aggiornati al 16/10: qwen3:8b sul server i3-2100, 100% CPU, senza quote Docker. Saluto con thinking 31 min 7,76 s, senza thinking 23,16 s; test verbose senza thinking 88 token a 1,76 token/s, prompt a 2,30 token/s. Run Cora dc904feb 41 min 54 s, quasi tutto nel modello. Qwen3:0.6b già disponibile e precedentemente misurato sul PC. Restano telemetria Ollama per run, valutazione controllata dei thread e router semantico/thinking con test di qualità e regressione." },
    { id: "DEP-01", state: "Parziale", label: "Verificare il deploy sul server", detail: "Inventario superato per servizi, storage, database, disponibilità modelli e bridge. Restano verifica dei backup, ripristino in ambiente separato e ciclo completo di una nuova release; il NAS richiede un backup distinto. L’accesso ai file di sistema in sola lettura va collaudato separatamente." },
  ],
  deferred: [
    { label: "Router semantico e thinking adattivo", detail: "Obiettivo di implementazione, non ancora certificato: riutilizzare Qwen3:0.6b come classificatore leggero solo nei casi ambigui, con scorciatoie deterministiche, soglia di incertezza e fallback. Decidere separatamente modello, thinking, contesto e tool; disattivare il thinking nei saluti e misurare il sovraccarico di routing. Nessun nuovo modello JEPA previsto." },
    { label: "Agente in background con modello grande locale", detail: "Da progettare per analisi approfondite e lavori lunghi non interattivi, avviati su richiesta e senza bloccare la chat di Cora. Valutare Colibrì con GLM-5.2 744B e, come alternativa sperimentale, kimi-k3-in-c: modelli MoE quantizzati con esperti caricati da disco e cache in RAM/VRAM, senza API cloud. Prima dell’integrazione misurare sul nostro hardware qualità, tempo al primo token, token/s, durata completa, RAM/VRAM e spazio/velocità SSD; i benchmark esterni non garantiscono le nostre prestazioni. Prevedere coda persistente, priorità alle attività interattive, stato e avanzamento in Attività, cancellazione manuale, salvataggio dei risultati e notifica finale, senza timeout rigido sulla durata del lavoro. Promemoria del 14/10/2026: agente non ancora implementato." },
    { label: "Taratura e valutazione dei modelli IA", detail: "Dedicare una revisione ai modelli: temperatura, top-p/top-k, thinking, quantizzazione, contesto e architetture dense/MoE. Misurare qualità, uso dei tool, RAM e latenza. Distinguere questa taratura dal fine-tuning dei pesi, da valutare separatamente." },
    { label: "Gestione avanzata documenti IA", detail: "Da progettare modifica strutturale Word/PDF, importazione da radici esterne autorizzate e ripristino agentico. Il ripristino della versione precedente richiede una destinazione libera: spostare prima il file corrente con la pagina File." },
    { label: "Storico delle consultazioni e ricerca estesa", detail: "Il pannello conserva fino a 200 passaggi dell’ultima richiesta nella sessione: ricaricamento e perdita di eventi non sono recuperabili. Da progettare uno storico privato per conversazione, ricerca indicizzata e OCR dei PDF scansionati. La ricerca attuale è lessicale, limitata a 2000 file esaminati e ai limiti di lettura per documento." },
    { label: "IDE avanzato e integrazione del codice attivo", detail: "L’editor del workspace e le consegne revisionabili sono disponibili. Linguaggio assistito e terminale restano futuri. L’applicazione al server è disponibile tramite il servizio updater e conferma del proprietario, dopo preparazione del rilascio." },
    { label: "Orchestratore autonomo", detail: "La delega del Supervisor è disponibile; l’orchestrazione autonoma resta rinviata." },
    { label: "Automodifica e attivazione autonoma", detail: "Il Programmatore è disponibile per bozze in workspace. L’applicazione autonoma al codice attivo e l’attivazione dei componenti restano rinviate." },
  ],
} as const;
