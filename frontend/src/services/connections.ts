import roadmap from "../../../docs/roadmap.json";

/** Fonte canonica condivisa con 17 passi.txt. Nessun inventario host pubblico. */
export const missingConnections = {
  files: {
    label: "Sincronizzazione delle copie IA",
    detail: "Originali e copie IA: sincronizzazione rinviata all’upgrade hardware.",
    endpoints: "Versioni e conflitti da definire dopo l’upgrade",
  },
  agentFileTools: {
    label: "Accesso File Server e gestione avanzata Libreria",
    detail: "Accesso e modifiche agentiche ai file server, importazione, cartelle e restore rinviati all’upgrade hardware.",
    endpoints: "Contratti tool e radici autorizzate rinviati",
  },
  graphEdit: {
    label: "Esecuzione delle automazioni grafiche",
    detail: "Le bozze grafiche sono disponibili; esecuzione e pianificazione restano da implementare.",
    endpoints: "Validazione, esecuzione e pianificazione da definire",
  },
} as const;
export type ConnectionKey = keyof typeof missingConnections;

export const homeRoadmap = {
  updatedAt: "18/10/2026",
  priorities: roadmap,
  paused: roadmap.filter(item=>item.state.includes("hardware")),
  serverEvidence: [{label:"Collaudo complessivo al punto 17",detail:"Le verifiche di sviluppo non attestano la versione installata o lo stato del server reale. Inventario e riscontri operativi restano privati."}],
  available: [
    {label:"Chat e runtime persistenti",detail:"Cronologia PostgreSQL, streaming, cancellazione cooperativa, permessi e approvazioni."},
    {label:"File e Libreria IA",detail:"Interfaccia file, allegati, consultazione Libreria e modifiche controllate già disponibili."},
    {label:"Storico consultazioni",detail:"Esiti delle capability, letture e contesti nella finestra ragionamento. Registro privato per conversazione, senza contenuti dei documenti."},
    {label:"Programmatore e updater",detail:"Workspace, verifiche e release su richiesta. Backup periodici cifrati disponibili dopo installazione e audit host."},
    {label:"Calendario, Audio e Tools",detail:"Funzioni già presenti; il collaudo integrato resta al punto 17."},
  ],
  next: roadmap.filter(item=>item.id==="FINAL"),
  deferred: roadmap.filter(item=>item.state.includes("hardware")||item.state==="Fuori scope"||item.state==="Escluso"),
} as const;
