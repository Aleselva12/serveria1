/** Permanent integration backlog, visible in Settings and next to unavailable controls. */
export const missingConnections = {
  graph: {
    label: "Grafo versionato del backend",
    detail:
      "La mappa dispone gli agenti del registro. Topologia, versioni e dipendenze dinamiche devono ancora arrivare dal backend.",
    endpoints: "GET /api/v1/architecture/graph; GET /api/v1/agents",
  },
  telemetry: {
    label: "Prestazioni del server",
    detail:
      "CPU, RAM, GPU, dischi, rete e cronologia: monitoraggio da collegare.",
    endpoints: "GET /api/v1/server/telemetry; GET /api/v1/server/storage",
  },
  services: {
    label: "Docker e altri servizi",
    detail: "Sono verificati solo FastAPI e la raggiungibilità di Ollama.",
    endpoints: "GET /api/v1/system/status",
  },
  history: {
    label: "Storico delle conversazioni",
    detail:
      "Le chat restano in questa pagina fino al ricaricamento. Il contesto del backend è volatile.",
    endpoints:
      "GET/POST /api/v1/conversations; GET /api/v1/conversations/{id}/messages",
  },
  streaming: {
    label: "Risposta progressiva",
    detail: "Cora restituisce la risposta completa al termine della richiesta.",
    endpoints: "GET /api/v1/runs/{id}/events (SSE)",
  },
  runs: {
    label: "Tracce di esecuzione",
    detail:
      "Passaggi, log, errori e conferme devono ancora essere esposti alla UI.",
    endpoints:
      "GET /api/v1/runs; GET /api/v1/runs/{id}; POST /api/v1/approvals/{id}",
  },
  code: {
    label: "Editor e progetti",
    detail:
      "Lettura, salvataggio, revisioni ed esecuzione del codice richiedono collegamenti e permessi backend.",
    endpoints:
      "/api/v1/workspaces; /api/v1/workspaces/{id}/files; /file; /executions",
  },
  calendar: {
    label: "Calendario personale",
    detail:
      "Gli eventi devono essere salvati sul server. Nessun agente calendario è previsto.",
    endpoints: "GET/POST/PATCH/DELETE /api/v1/calendar/events",
  },
  files: {
    label: "File del server",
    detail:
      "Cartelle, ricerca, spazio, upload, download, eliminazione e condivisione del NAS sono da collegare.",
    endpoints:
      "/api/v1/server/files/tree; /folders/{id}/children; /api/v1/files; /download; /preview; /processing; /shares",
  },
  attachments: {
    label: "Allegati della chat",
    detail:
      "Il caricamento e il collegamento dei file alle richieste di Cora non sono ancora disponibili.",
    endpoints:
      "POST /api/v1/files; POST /api/v1/conversations/{id}/messages con attachmentIds",
  },
  audio: {
    label: "Microfono e trascrizione dalla UI",
    detail: "Acquisizione e invio audio al backend sono da collegare.",
    endpoints: "Contratto upload/trascrizione da definire",
  },
  permissions: {
    label: "Permessi e configurazione completa",
    detail:
      "Il registro descrive capacità strutturali; non verifica permessi dell’utente né readiness degli agenti.",
    endpoints:
      "GET /api/v1/permissions; GET /api/v1/system/config; autenticazione/sessioni da definire",
  },
  graphEdit: {
    label: "Modifica dell’architettura",
    detail:
      "La mappa è in sola lettura. Modifiche e automazioni richiedono API dedicate.",
    endpoints:
      "Contratti versionati per bozze, validazione e pubblicazione da definire",
  },
} as const;
export type ConnectionKey = keyof typeof missingConnections;
