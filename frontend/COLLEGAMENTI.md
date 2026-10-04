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
| Calendario | `/api/v1/calendar/events`, storico/ripristino e proposte | `calendarApi.ts` |
| Memoria | `/memory`, `/memory/context`, `/memory/episodes`, `/memory/working` | `api.ts` |

SSE mostra token provvisori, aggiornamenti dello stato e risultato finale; il risultato persistito resta autorevole. Sono collegati timeout e stop cooperativo; lo stop non annulla gli effetti già avvenuti. Il pannello delle proposte non continua automaticamente il ragionamento del modello.

Allegati chat e gestione delle registrazioni salvate sono collegati: vedere la sezione «Allegati della chat, file avanzati e registrazioni audio» del README principale. Il microfono non è richiesto. Restano predisposizioni l’esecuzione/pianificazione delle bozze e l’agente programmatore/editor eseguibile.



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
