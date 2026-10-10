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
  updatedAt: "10/10/2026",
  available: [
    { label: "Copie e modifiche controllate nella Libreria IA", detail: "Copie senza sovrascrittura; modifiche testuali e aggiunte Word approvate in Attività e legate alla versione letta. Cestino solo dopo conferma, senza eliminazione definitiva. Versione precedente conservata nel cestino prima della modifica." },
    { label: "Consultazione agentica Libreria IA", detail: "Tre tool di sola lettura disponibili durante le richieste automatiche, ricerca lessicale per nome e contenuto, percorsi delle fonti e pannello attività in chat. La selezione manuale dei tool prevale. Nessuna ricerca in background." },
    { label: "Chat e memoria persistenti", detail: "Cronologia, streaming, gestione e versioni della memoria e contesto permanente." },
    { label: "Accesso, permessi e approvazioni", detail: "Login del proprietario, policy delle capability e proposte consultabili in Attività." },
    { label: "Runtime e diagnostica", detail: "Coda, stati persistenti, cancellazione cooperativa, registro operazioni, bus eventi e profilazione." },
    { label: "File, calendario e Tools", detail: "File server e Libreria IA con anteprime, ricerca ricorsiva, condivisioni private e upload riprendibili; calendario e bozze delle automazioni." },
    { label: "Programmatore", detail: "Copilot, workspace isolati, 21 strumenti, skill, registro componenti, consegne ZIP e verifiche Python/contratti/TypeScript/build frontend. Preparazione, pubblicazione, applicazione e rollback delle release seguono i controlli previsti; nessuna attivazione autonoma." },
    { label: "Allegati chat, selezione tool e Audio", detail: "Documenti allegati alle richieste, tool automatici o selezionati manualmente per il singolo invio e pagina Audio per registrazioni salvate, trascrizione locale, correzioni ed esportazione." },
  ],
  next: [
    { label: "Collaudare Libreria IA con Ollama", detail: "Verificare scelta autonoma dei tool, permessi, fonti e streaming con documenti reali sul server. I test simulati non certificano il comportamento del modello." },
    { label: "Collaudare il Programmatore sul server", detail: "Preparare le immagini Docker Python e frontend, verificare percorsi e isolamento ed eseguire una richiesta reale con il modello Ollama. I test del repository non certificano il modello o il deployment." },
    { label: "Misurare la latenza sul PC reale", detail: "Usare la profilazione in Attività per distinguere attesa, contesto, modello e tool prima di scegliere gli interventi." },
    { label: "Verificare il deploy sul server", detail: "Il profilo Docker Debian e le istruzioni di backup/ripristino sono presenti; verificare percorsi, modelli locali, accesso via Tailscale e ripristino sulla macchina finale." },
  ],
  deferred: [
    { label: "Gestione avanzata documenti IA", detail: "Da progettare modifica strutturale Word/PDF, importazione da radici esterne autorizzate e ripristino agentico. Il ripristino della versione precedente richiede una destinazione libera: spostare prima il file corrente con la pagina File." },
    { label: "Storico delle consultazioni e ricerca estesa", detail: "Il pannello conserva fino a 200 passaggi dell’ultima richiesta nella sessione: ricaricamento e perdita di eventi non sono recuperabili. Da progettare uno storico privato per conversazione, ricerca indicizzata e OCR dei PDF scansionati. La ricerca attuale è lessicale, limitata a 2000 file esaminati e ai limiti di lettura per documento." },
    { label: "IDE avanzato e integrazione del codice attivo", detail: "L’editor del workspace e le consegne revisionabili sono disponibili. Linguaggio assistito, terminale e applicazione delle modifiche al server non fanno parte del flusso attuale; l’integrazione resta manuale." },
    { label: "Orchestratore autonomo", detail: "La delega del Supervisor è disponibile; l’orchestrazione autonoma resta rinviata." },
    { label: "Automodifica e attivazione autonoma", detail: "Il Programmatore è disponibile per bozze in workspace. L’applicazione autonoma al codice attivo e l’attivazione dei componenti restano rinviate." },
  ],
} as const;
