# Collegamenti correnti

Frontend e backend sono aggiornati insieme in `serveria1`; `/backend` è il prefisso del proxy, rimosso prima di FastAPI. Tutte le operazioni richiedono la sessione personale, eccetto login e stato di autenticazione. I servizi UI usano `services/transport.ts`.

| Area | API backend | Adattatore frontend |
| --- | --- | --- |
| Accesso | `/auth/status`, `/auth/login`, `/auth/logout` | `AuthGate`, `transport.ts` |
| Home | `/health`, `/api/v1/server/telemetry`, `/api/v1/system/status` | `api.ts`, `useBackend.ts` |
| Chat | `/conversations`, `/conversations/{id}/messages`, `/api/v1/chat/runs`, `/api/v1/runtime/runs/{id}/events` | `api.ts`, `runtimeApi.ts`, `useConversations.ts` |
| Stop/stato | `/api/v1/runtime`, `/api/v1/runtime/runs/{id}`, `/api/v1/runtime/runs/{id}/cancel` | `runtimeApi.ts`, `RuntimePanel` |
| Framework | `/api/v1/architecture/overview`, `/api/v1/architecture/graph` | `api.ts` |
| Tracce | `/api/v1/runs`, `/api/v1/runs/{id}` | `api.ts`, `ArchitectureRuntime` |
| Catalogo tools | `/tools/inventory`, `/tools/definition` | `api.ts`, `toolsApi.ts` |
| Registry/permessi | `/api/v1/runtime/registry`, `/api/v1/runtime/policies` | `runtimeApi.ts`, `RuntimePanel` |
| Approvazioni | `/api/v1/approvals`, `/api/v1/approvals/{id}/resolve`, `/api/v1/approvals/calendar/{id}/resolve` | `runtimeApi.ts`, `RuntimePanel` |
| Bozze grafiche | `/tools/drafts` e dettaglio per ID | `toolsApi.ts` |
| File server | `/api/v1/server/files/*` | `filesApi.ts` |
| Libreria IA | `/api/v1/library/files/*` | `filesApi.ts` |
| Programmatore | `/api/v1/programmer/workspaces/*`, `/api/v1/programmer/runs` | `programmerApi.ts`, `Programmer`, `WorkspaceEditor`, `ProgrammerArtifacts` |
| Calendario | `/api/v1/calendar/events`, storico/ripristino e proposte | `calendarApi.ts` |
| Memoria | `/memory`, `/memory/context`, `/memory/episodes`, `/memory/working` | `api.ts` |

SSE mostra token provvisori, aggiornamenti dello stato e risultato finale; il risultato persistito resta autorevole. Sono collegati timeout e stop cooperativo; lo stop non annulla gli effetti già avvenuti. Il pannello delle proposte non continua automaticamente il ragionamento del modello.

Allegati chat e gestione delle registrazioni salvate sono collegati: vedere la sezione «Allegati della chat, file avanzati e registrazioni audio» del README principale. Il microfono non è richiesto. Restano predisposizioni l’esecuzione/pianificazione delle bozze e l’automodifica del codice attivo. Il Programmatore è collegato e lavora su workspace isolati.



## Nuovi adapter e percorsi

```text
src/
├── App.tsx                        # graffetta, allegati della richiesta e menu Audio
├── components/
│   ├── Audio.tsx                  # caricamento, stato, correzioni, download e copia IA
│   ├── FileManager.tsx            # anteprime, ricerca ricorsiva, link e ripresa upload
│   └── FilePreview.tsx            # visualizzazione sicura dell’anteprima
└── services/
    ├── mediaApi.ts                # /api/v1/chat/attachments e /api/v1/audio
    ├── runtimeApi.ts              # attachment_ids, run, streaming e annullamento
    ├── useConversations.ts        # riferimenti agli allegati nella cronologia
    ├── filesApi.ts                # /preview, /search, /shares, /uploads
    └── fileHash.ts                # SHA-256 incrementale senza caricare tutto in RAM
```

I contratti completi, i limiti e la migrazione SQL sono descritti nel README
principale. I link condivisi richiedono login e accesso alla rete privata.

## Chat: allegati e tool per richiesta

`POST /api/v1/chat/attachments` carica documenti della conversazione; l’invio chat contiene `attachment_ids`. Il pulsante Allega è visibile e gli estratti limitati sono segnalati. Per gli audio usare la pagina Audio.

`GET /api/v1/chat/tools` restituisce i tool del Supervisor, comprese le deleghe agli specialisti e le policy correnti. Il selettore manuale invia `manual_tools` a `POST /api/v1/chat/runs`; la scelta vale per il singolo invio, torna automatica dopo l’invio riuscito e viene recuperata con la bozza in caso di errore. `null` usa il routing automatico, `[]` esclude gli strumenti. La selezione non esegue azioni direttamente e non concede approvazioni. Nessuna conferma per policy `auto`; conferme solo dove previste.

## Catalogo Tools: API dirette e integrazioni mancanti

Le API dirette di interfaccia/servizio sono elencate a parte, con stato `direct`. Le operazioni File Server/Libreria IA con wrapper agenti previsto ma assente hanno stato `integration_needed` e indicano il tool da creare. I tool dichiarati ma non assegnati hanno stato `unconnected`; i promemoria di implementazione sono `planned`. L’intenzione di integrazione è dichiarata in `core/tool_backlog.py`, non dedotta dal fatto che un endpoint esista. Vedere `docs/TOOLS_BACKLOG.md`.

Le automazioni grafiche restano bozze: nessuna esecuzione, pianificazione o assegnazione agli agenti. Gli allegati chat sono implementati; il microfono live è opzionale e rinviato.
