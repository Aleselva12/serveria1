# Audit README Serveria/Cora â€” 25 ottobre 2026

## Perimetro e metodo

Base: `a8fb19d6acfdec39c65c6c710e4f7769f9c3db3b` (main, merge #92). Branch separato `docs/readme-audit-20261025`; solo documentazione, nessun merge/deploy/accesso Debian o dati reali. Inventario ricavato dallâ€™intero elenco dei file versionati, senza affidarsi alla ricerca GitHub indicizzata. Le directory sincronizzate del progetto non sono state modificate.

Al controllo iniziale GitHub: nessuna PR aperta; #84 merged il 24 ottobre, merge `441f006e199ea5125ce6f4a62c2169c7073724f1`. Il suo branch esiste ancora ma non Ã¨ la base di lavoro. Branch remoti censiti: main; audit/consolidation-calendar-docs-20261024; codex/agent-cards-model-routing; codex/agent-model-verification; codex/fix-desktop-agent-save; copilot/check-security-concerns; feature/adaptive-chat-20261025; feature/machines-all-installed-models-20261024; feature/machines-tailnet-workers-20261024; fix/machines-auth-diagnostics-toggle-20261024; snapshots/20261024T023811Z-0ecb15de46d3. La presenza di un branch non ne prova integrazione o operativitÃ .

Livelli usati: **implementato** = sorgente presente; **collegato** = richiamato da grafo/router/UI/configurazione; **test previsto** = test/workflow presente, distinto da un risultato osservato; **Debian verificato** = prova datata con versione e ambiente, non inferibile dal codice. I documenti storici contengono riscontri dellâ€™operatore e test precedenti: non sono stati ripetuti e non attestano la release attiva odierna.

## Inventario esaustivo prima delle modifiche

Otto README versionati, nessun altro README annidato o con diversa capitalizzazione nellâ€™albero Git della base.

| README | RealtÃ  descritta | Fonti primarie confrontate |
| --- | --- | --- |
| [Root](../README.md) | Avvio, sei ruoli, runtime, permessi, dati, UI/file/audio | api.py, graph.py, tools.py, core, grafi specialisti, compose, env, frontend, tests, docs |
| [Contesto](../context_pages/README.md) | Selezione pagine/tool e dati proprietario | core/context_pages.py, core/chat_tools.py, graph.py, context_pages/*.md, test_context_pages/owner_context_pages/chat_tools |
| [Database](../database/README.md) | Persistenza PostgreSQL/pgvector | core/database.py, schema.sql, migrations, compose database/server, test PostgreSQL |
| [Migrazioni](../database/migrations/README.md) | Versioni/checksum e aggiornamenti | core/database.py, cinque SQL numerati, test_database_migration_contract, updater/engine.py |
| [Deploy](../deploy/README.md) | Compose, audio, backup/restore, autenticazione e mount | compose*.yml, Dockerfile, deploy/manage.py/doctor.py/tailscale_login.py/project_files.py, env esempio, ci_verify.py |
| [Frontend](../frontend/README.md) | Pagine, sessioni, proxy, SSE e tool | App.tsx, components, services, types, vite.config.ts, package.json/lock, tests |
| [Programmatore](../programmer_agent/README.md) | Snapshot/Git, 21 tool, cinque skill, check/consegne | programmer_tools.py, workspace.py, checks.py, components.py, knowledge.py, releases.py, context/router, Dockerfile check |
| [Updater](../updater/README.md) | Servizio host, release, bridge e recupero | setup.py, service.py, engine.py, check_runner.py, data_backups.py, managed_apps.py, tests/test_updater.py |

## Confronto sistematico per componente

| Ambito | Implementazione e collegamento osservati | Prove previste / limite operativo |
| --- | --- | --- |
| Avvio/autenticazione | AVVIO.ps1; core/auth.py; middleware e router in api.py; AuthGate/transport; modalitÃ  password/desktop/tailscale | test_desktop_auth_update, test_tailscale_auth; nessun login remoto reale ripetuto |
| Agentica | Supervisor piÃ¹ Structure, Programmer, Research, Audio, Email; bind capability, contratti/permission engine e dispatcher | test_capability_contracts/core_protocol/graph_fastpath; modello simulato non misura qualitÃ  Ollama |
| Runtime/governance | runtime/run_lifecycle/operation_journal, SQL, runtime_api e RuntimePanel; un processo applicativo | test_durable_runtime/runtime_postgres; nessuna garanzia di exactly-once esterna o coordinamento distribuito |
| Modelli/macchine | models/agent_models/model_profiles/machines_api, worker/worker.py, UI Architecture/Machines | test_agent_models/model_profiles/worker_chat; metadati dichiarati, trasporto remoto bufferizzato, nessun collaudo GPU/worker reale |
| Contesto/memoria | context_pages/context_budget/background_embeddings/memory/system_context; chiamanti nei grafi e UI memoria | test_context_pages/owner_context_pages/memory_context/adaptive_context; sintesi/embedding richiedono modello e DB reali |
| File/Libreria | server_files/file_paths/file_extras/ia_library/library_*; FileManager e servizi HTTP | test_server_files/file_extras/library_*; protezioni e limiti statici non certificano mount NAS reali |
| Allegati/audio/Word | chat_attachments/audio_api/commercial_notes/commercial_word; Audio/CommercialNotes; migrazioni 0002/0006 | test_chat_attachments/audio_ui/commercial_*; Whisper/diarizzazione/Word autentici restano da collaudare |
| Calendario Google/locale | calendar/calendar_api/calendar_tools/google_calendar, approvazioni e Calendar UI | test_calendar/google_calendar/google_calendar_approvals; provider simulato, nessun OAuth reale o gestione duplicati storici verificata |
| Email/preventivi | email_agent connector/tools/grafo, Gmail bozze e PDF; invio bloccato | API/provider e credenziali reali non provati; non equivale a risposta automatica alle email |
| Progetti/push/foto | conversation_projects/consultations/webpush/notifications, sidebar e viste mobili | test_consultations/webpush/media_postgres; permessi browser e backup foto reale non verificati |
| Programma | API, 21 tool, snapshot e bridge Git, check/componenti/consegne, UI Programma | test_programmer_*/frontend_check_cache; cinque skill Cora, non installazioni ChatGPT; Graphify opzionale |
| Updater/app esterne | engine/service/setup/check_runner, system update UI, managed_apps bridge | test_updater/managed_apps/home_updater_bridge; Magazzino Tele esterno, stato dâ€™installazione non attestato |
| Terminale personale | terminal_service, compose.terminal.yml, setup/Nginx/UI Home | test_terminal e personal-terminal frontend; opzionale, assente dai servizi Compose base |
| Deployment | Compose base postgres/api/web, Dockerfile target, state persistente, Ollama esterno | workflow verify: Linux+PG, Windows, deployment api/audio, terminale; nessun daemon accessibile nel controllo iniziale |
| Documenti/stato | docs/FUNCTIONALITY_STATUS, SERVER_VALIDATION, rapporti consolidamento e chat adattiva | prove storiche con data/versione, non inventario vivo Debian; roadmap non certifica completamento |

## Checkpoint 1 â€” root e persistenza

README revisionati: root, database, database/migrations. Corretti conteggio deleghe, precedenza modelli, timeout disattivati per default, stato test Google, confine automodifica autonoma/rilascio richiesto; aggiunti percorsi mancanti e versioni migrazioni. Rimossa lâ€™affermazione non verificata sullo stato di una repository frontend esterna. Esplicitata esposizione porta nel Compose DB locale e distinzione storage SQL/file.

Verificato staticamente: migrazioni 0001â€“0006, checksum/ordine/lock, modello default e precedenze, generation_policy, router e UI. Non verificabili qui: schema/immagini/versione effettiva su Debian, account esterni, mount, accelerazione AMD, restore reale. CI base [Verify backend and frontend](https://github.com/Aleselva12/serveria1/actions/runs/40139389679) e [CodeQL](https://github.com/Aleselva12/serveria1/actions/runs/40139389475) osservate queued, non superate.

## Checkpoint 2 — contesto, frontend, Programmatore

README revisionati: context_pages, frontend, programmer_agent (commit `c3e7005`). Eliminato il riferimento alla branch sperimentale; documentati frontmatter/esclusione README, routing Libreria e scelta manuale; aggiornati autenticazione, chat adattiva, Macchine e servizi opzionali; conteggio 21 capability e cinque skill corretto. Verificati chiamanti graph/API/UI e liste effettive. Non verificati: inferenza reale, worker aggiornato, qualità tool, servizi esterni e check Docker del deployment.

## Checkpoint 3 — deploy e updater

README revisionati: deploy, updater. Corretta precedenza modello e modalità desktop, distinta porta init/fallback; documentati OAuth Calendar separato, servizi opzionali e natura distruttiva delle fixture CI. Corretta l’assenza dichiarata di lavori periodici: backup dati host opzionali presenti. Distinti unit test simulati e prova Docker reale prevista in CI, senza promuoverla a successo osservato. Verificati percorsi manage/engine/setup/runner/backup, Dockerfile/Compose/Nginx e workflow. Non eseguiti deploy, release, restore, OAuth o backup sul server.
