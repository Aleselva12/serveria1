/** Collegamenti ancora incompleti. Le funzioni già operative non appartengono al backlog. */
export const missingConnections = {
  files: {
    label: "Sincronizzazione delle copie IA",
    detail: "Anteprime, ricerca nelle sottocartelle, link privati revocabili e upload riprendibili sono collegati. La sincronizzazione bidirezionale fra originali e copie IA resta un lavoro futuro.",
    endpoints: "Contratto di sincronizzazione e gestione conflitti da definire",
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
    { label: "File, calendario e Tools", detail: "File server e Libreria IA con anteprime, ricerca ricorsiva, condivisioni private e upload riprendibili; calendario e bozze delle automazioni." },
    { label: "Programmatore", detail: "Copilot, workspace isolati, 14 strumenti, skill, registro componenti, consegne ZIP e verifiche Python/contratti/TypeScript/build frontend. Mappa Graphify opzionale con ricerca ed esplorazione. Integrazione e attivazione restano manuali." },
    { label: "Allegati chat e Audio", detail: "Documenti allegati alle richieste e pagina Audio per registrazioni salvate, trascrizione locale, correzioni ed esportazione." },
  ],
  next: [
    { label: "Misurare la latenza sul PC reale", detail: "Usare la profilazione in Attività per distinguere attesa, contesto, modello e tool prima di scegliere gli interventi." },
    { label: "Verificare il deploy sul server", detail: "Il profilo Docker Debian e le istruzioni di backup/ripristino sono presenti; verificare percorsi, modelli locali, accesso via Tailscale e ripristino sulla macchina finale." },
  ],
  deferred: [
    { label: "Orchestratore autonomo", detail: "La delega del Supervisor è disponibile; l’orchestrazione autonoma resta rinviata." },
    { label: "Automodifica e attivazione autonoma", detail: "Il Programmatore è disponibile per bozze in workspace. L’applicazione autonoma al codice attivo e l’attivazione dei componenti restano rinviate." },
  ],
} as const;

