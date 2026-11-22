// Plain-language names for the server's tools. The inventory exposes function names
// ("programmer_register_component"); the page shows these titles instead. Tools not
// listed here still work: they appear under "Strumenti tecnici" with a cleaned-up name.

export type Area = "Server" | "Mail" | "Calendario" | "Documenti" | "Memoria" | "Audio" | "Assistenti" | "Strumenti tecnici";
export const AREAS: Area[] = ["Server", "Mail", "Calendario", "Documenti", "Memoria", "Audio", "Assistenti", "Strumenti tecnici"];
export type Guide = { title: string; hint: string; area: Area; essential?: boolean };

const G: Record<string, Guide> = {
  // Server
  system_status_tool: { title: "Stato del server", hint: "CPU, memoria e disco in questo momento", area: "Server", essential: true },
  recent_system_events_tool: { title: "Ultimi eventi del server", hint: "Cosa è successo di recente: avvii, errori, avvisi", area: "Server", essential: true },
  calculator_tool: { title: "Calcolatrice", hint: "Fa un calcolo, es. 6*7", area: "Server", essential: true },
  owner_context_tool: { title: "Le mie preferenze", hint: "Il contesto personale che hai salvato per Cora", area: "Server" },
  // Mail
  get_daily_emails: { title: "Mail di un giorno", hint: "Le mail ricevute in una data (vuoto = oggi)", area: "Mail", essential: true },
  search_email_archive: { title: "Cerca nelle mail", hint: "Trova mail per mittente, oggetto o parole", area: "Mail", essential: true },
  get_email_by_id: { title: "Apri una mail", hint: "Legge una mail precisa dal suo identificativo", area: "Mail" },
  save_email_draft: { title: "Prepara una bozza di mail", hint: "Salva una bozza in Gmail, non la invia mai", area: "Mail", essential: true },
  generate_quote_pdf: { title: "Crea un preventivo PDF", hint: "Genera un preventivo con righe e prezzi", area: "Mail" },
  // Calendario
  calendar_list_events: { title: "Appuntamenti del periodo", hint: "Gli eventi fra due date", area: "Calendario", essential: true },
  calendar_get_event: { title: "Apri un appuntamento", hint: "I dettagli di un evento preciso", area: "Calendario" },
  calendar_create_event: { title: "Proponi un appuntamento", hint: "Nuovo evento, lo approvi tu prima che venga salvato", area: "Calendario", essential: true },
  calendar_update_event: { title: "Modifica un appuntamento", hint: "Cambia un evento, con la tua approvazione", area: "Calendario" },
  calendar_delete_event: { title: "Cancella un appuntamento", hint: "Rimuove un evento, con la tua approvazione", area: "Calendario" },
  // Documenti
  search_local_documents: { title: "Cerca nei documenti", hint: "Trova parole nei tuoi documenti e PDF", area: "Documenti", essential: true },
  library_search: { title: "Cerca nella Libreria IA", hint: "Trova parole nei documenti della Libreria IA", area: "Documenti", essential: true },
  read_local_document: { title: "Leggi un documento", hint: "Apre un testo, Word o PDF", area: "Documenti" },
  library_read: { title: "Leggi dalla Libreria IA", hint: "Apre un documento della Libreria IA", area: "Documenti" },
  list_local_documents: { title: "Elenco dei documenti", hint: "Quali documenti ci sono", area: "Documenti" },
  library_list: { title: "Elenco della Libreria IA", hint: "Quali documenti ci sono nella Libreria IA", area: "Documenti" },
  create_word_document: { title: "Crea un documento Word", hint: "Scrive un nuovo file .docx", area: "Documenti", essential: true },
  append_word_document: { title: "Aggiungi a un Word", hint: "Aggiunge testo in fondo a un documento", area: "Documenti" },
  // Memoria
  recall_memory_tool: { title: "Cosa ricorda Cora", hint: "Cerca fra le cose che Cora ha memorizzato", area: "Memoria", essential: true },
  remember_tool: { title: "Fai ricordare qualcosa", hint: "Salva un'informazione nella memoria di Cora", area: "Memoria", essential: true },
  forget_memory_tool: { title: "Fai dimenticare qualcosa", hint: "Cancella un ricordo preciso", area: "Memoria" },
  // Audio
  list_audio_files: { title: "Elenco degli audio", hint: "Quali registrazioni ci sono", area: "Audio" },
  transcribe_audio_file: { title: "Trascrivi un audio", hint: "Trasforma una registrazione in testo", area: "Audio", essential: true },
  save_transcript: { title: "Salva una trascrizione", hint: "Scrive il testo trascritto in un file", area: "Audio" },
  // Assistenti (deleghe)
  email_agent_tool: { title: "Chiedi all'assistente mail", hint: "Gli dai un compito sulle mail, ad esempio riassumere", area: "Assistenti", essential: true },
  search_agent_tool: { title: "Chiedi all'assistente documenti", hint: "Cerca e analizza i tuoi documenti per te", area: "Assistenti", essential: true },
  audio_agent_tool: { title: "Chiedi all'assistente audio", hint: "Trascrive e analizza registrazioni", area: "Assistenti" },
  structure_agent_tool: { title: "Chiedi all'assistente piani", hint: "Prepara piani e valutazioni", area: "Assistenti" },
  programmer_agent_tool: { title: "Chiedi al programmatore", hint: "Crea nuovi strumenti in un'area di prova", area: "Assistenti" },
};

const TECH: Record<string, string> = {
  list_project_files: "Elenco file del progetto", read_project_file: "Leggi file del progetto", structure_registry_tool: "Componenti di Cora",
  structure_components: "Componenti di Cora", structure_memory_status: "Statistiche della memoria", structure_recent_events: "Eventi tecnici recenti",
  structure_control_snapshot: "Fotografia tecnica del sistema", structure_system_status: "Stato del server (tecnico)",
  structure_list_project_files: "Elenco file del progetto", structure_read_project_file: "Leggi file del progetto",
  structure_owner_status: "Responsabile dei piani", structure_permission_manifest: "Regole dei permessi",
  structure_save_plan: "Salva un piano", structure_save_evaluation: "Salva una valutazione", structure_save_management: "Salva uno stato di lavoro",
  structure_list_artifacts: "Elenco piani salvati", structure_read_artifact: "Leggi un piano salvato",
};

export function guideFor(name: string): Guide {
  const known = G[name];
  if (known) return known;
  const tech = TECH[name];
  if (tech) return { title: tech, hint: "Strumento tecnico", area: "Strumenti tecnici" };
  const plain = name.replace(/^programmer_/, "Programmatore: ").replace(/_tool$/, "").replace(/_/g, " ").trim();
  return { title: plain ? plain[0].toUpperCase() + plain.slice(1) : name, hint: "Strumento tecnico", area: "Strumenti tecnici" };
}

// Labels for parameter names; unknown ones are shown with underscores turned into spaces.
const PARAMS: Record<string, string> = {
  query: "Cosa cercare o chiedere", expression: "Calcolo", relative_path: "Percorso del file", directory: "Cartella",
  recursive: "Anche nelle sottocartelle", extension: "Tipo di file", max_results: "Quanti risultati al massimo", limit: "Quanti al massimo",
  start: "Dal (data e ora)", end: "Al (data e ora)", title: "Titolo", notes: "Note", all_day: "Tutto il giorno", reason: "Motivo",
  event_id: "Identificativo evento", version: "Versione", day_iso: "Giorno (AAAA-MM-GG, vuoto = oggi)", message_id: "Identificativo mail",
  to_email: "Destinatario", subject: "Oggetto", body: "Testo", content: "Contenuto", filename: "Nome del file", overwrite: "Sovrascrivi se esiste",
  heading: "Titolo della sezione", memory_type: "Tipo di ricordo", key: "Argomento", importance: "Importanza", memory_id: "Identificativo ricordo",
  language: "Lingua", diarize: "Distingui chi parla", expected_speakers: "Numero di persone", transcript: "Testo trascritto",
  source_audio_path: "File audio", customer_name: "Cliente", items_json: "Righe del preventivo (JSON)", quote_number: "Numero preventivo",
  quote_date: "Data", customer_address: "Indirizzo cliente", vat_percent: "IVA %", thread_id: "Conversazione", event_type: "Tipo di evento",
  component: "Componente", kind: "Tipo", workspace_id: "Area di lavoro",
};
export function paramLabel(name: string) {
  return PARAMS[name] ?? name.replace(/_/g, " ");
}
