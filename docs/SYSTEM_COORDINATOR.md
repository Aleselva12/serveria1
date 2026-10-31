# System Coordinator — Gruppo B

Il **System Coordinator** è la vista di coordinamento interna di Cora. Nella prima
versione è deliberatamente **read-only**: non introduce un secondo runtime, non
esegue tool, non sceglie agenti e non cambia worker o modelli.

## Principio

Ogni tipo di stato deve avere una sola fonte autorevole. Le altre viste sono
repliche operative o diagnostiche e non devono essere usate per correggere
silenziosamente la fonte canonica.

| Stato | Fonte autorevole | Note |
| --- | --- | --- |
| lifecycle task/run | `runtime_runs` PostgreSQL / `core.run_lifecycle` | root e child run, revisioni, cancellazione, esito |
| esecuzione live | `core.runtime.Run` | solo stato effimero del processo corrente |
| comunicazione componenti | `TaskEnvelope` / `ComponentResult` | contratto tipizzato in-process |
| eventi critici | domain events PostgreSQL | transazionali |
| eventi live | `EventBus` | replay limitato, non storico autorevole |
| diagnostica | `diagnostic_events` PostgreSQL | best-effort; non prova l'assenza di un'azione |
| working memory | `working_memory` PostgreSQL | stato operativo temporaneo, non lifecycle |
| memoria cognitiva | memories / episodes / system context | separata da log e cronologia |
| permessi | `core.permissions` + `action_approvals` | deterministico |
| risorse | machine registry + agent bindings | manuale nella fase attuale |
| selezione contesto | context pages / context budget | il Context Manager globale resta da progettare |

## API

`GET /api/v1/runtime/coordinator` restituisce uno snapshot aggregato dei sistemi
esistenti e il manifest di ownership. Lo snapshot non esegue azioni.

## Confini attuali

Il Coordinator **non**:
- pianifica la richiesta utente;
- modifica permessi;
- seleziona automaticamente worker o modelli;
- ritenta effetti di scrittura;
- decide recovery;
- sostituisce il Context Manager.

Queste funzioni restano separate fino a una decisione architetturale esplicita.
