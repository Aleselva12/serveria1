/** Collegamenti ancora incompleti. Le funzioni già operative non appartengono al backlog. */
export const missingConnections = {
  code: {
    label: "Editor e progetti",
    detail: "La pagina Programma e il pannello copilot sono predisposti. Lettura, salvataggio, revisioni ed esecuzione del codice richiedono API e permessi dedicati.",
    endpoints: "Contratti workspace/file/esecuzioni da definire",
  },
  files: {
    label: "Funzioni aggiuntive dei file",
    detail: "File server e Libreria IA sono collegati. Restano anteprime, ricerca ricorsiva, condivisioni e upload riprendibile; la sincronizzazione delle copie IA è un lavoro futuro.",
    endpoints: "Contratti per anteprime, condivisioni, upload riprendibile e sincronizzazione da definire",
  },
  attachments: {
    label: "Allegati della chat",
    detail: "File server e Libreria IA hanno già il caricamento. Manca il collegamento degli allegati a una richiesta nella chat.",
    endpoints: "Contratto allegati della conversazione e accesso degli agenti da definire",
  },
  audio: {
    label: "Microfono e trascrizione dalla UI",
    detail: "L’agente Audio può trascrivere file locali. Restano acquisizione dal microfono, invio e gestione della trascrizione nell’interfaccia.",
    endpoints: "Contratto acquisizione/upload/trascrizione dalla UI da definire",
  },
  graphEdit: {
    label: "Esecuzione delle automazioni grafiche",
    detail: "La mappa agentica è consultabile e Tools permette di modificare bozze grafiche. Mancano esecuzione e pianificazione delle bozze e modifica operativa dell’architettura.",
    endpoints: "API di esecuzione/pianificazione e modifica dell’architettura da definire",
  },
} as const;
export type ConnectionKey = keyof typeof missingConnections;

/** Stato del codice verificato su main; distinto dalla disponibilità dei servizi. */
export const homeRoadmap = {
  updatedAt: "04/10/2026",
  available: [
    { label: "Chat e memoria persistenti", detail: "Cronologia, streaming, gestione e versioni della memoria e contesto permanente." },
    { label: "Accesso, permessi e approvazioni", detail: "Login del proprietario, policy delle capability e proposte consultabili in Attività." },
    { label: "Runtime e diagnostica", detail: "Coda, stati persistenti, cancellazione cooperativa, registro operazioni, bus eventi e profilazione." },
    { label: "File, calendario e Tools", detail: "File server e copie nella Libreria IA, calendario mese/giorno e bozze delle automazioni." },
  ],
  next: [
    { label: "Misurare la latenza sul PC reale", detail: "Usare la profilazione in Attività per distinguere attesa, contesto, modello e tool prima di scegliere gli interventi." },
    { label: "Verificare il deploy sul server", detail: "Il profilo Docker Debian e le istruzioni di backup/ripristino sono presenti; verificare percorsi, modelli locali, accesso via Tailscale e ripristino sulla macchina finale." },
  ],
  deferred: [
    { label: "Orchestratore autonomo", detail: "La delega del Supervisor è disponibile; l’orchestrazione autonoma resta rinviata." },
    { label: "Agente programmatore e automodifica", detail: "Da affrontare dopo misure delle prestazioni e definizione dei permessi sui progetti." },
  ],
} as const;
