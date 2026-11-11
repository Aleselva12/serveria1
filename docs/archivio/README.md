# Archivio documentale

Fotografie datate: diagnosi, verifiche e revisioni legate a un commit o a una
PR precisi. Descrivono lo stato **di quel momento**, non quello attuale; il codice
e il commit attivo prevalgono sempre (vedi `docs/AGENT_CONTEXT.md`, regola 3).

Un documento entra qui solo dopo averne letto le decisioni: quelle ancora valide
vanno prima riportate in [`../DECISIONI.md`](../DECISIONI.md). "Non citato da nessun
file" non significa "obsoleto".

| Documento | Fotografia di |
| --- | --- |
| `CLOSURE_ROUTING_20261016.md` | chiusura Home e routing, 16 ottobre 2026 |
| `consolidation-services-20261024.md` | verifica della PR Draft #84, 24 ottobre 2026 |
| `desktop-update-and-response-recovery.md` | diagnosi del run 92805733, 18 ottobre 2026 |
| `programmer-context-overflow.md` | riscontro locale del 18 ottobre 2026 |
| `priority-tree-fix-2026-11-06.md` | correzioni di Priorità e mappa, 6 novembre 2026 |
| `code-scanning-review.md` | revisione di 73 avvisi CodeQL sulla baseline dopo la PR #24 |

Gli altri audit datati (`AUDIT_CLOSURE.md`, `README_AUDIT_20261025.md`,
`CONSOLIDAMENTO_20261018.md`) restano in `docs/`: sono citati per percorso da altri
documenti (il primo da `PROJECT_WORK.md`, il secondo da `README.md`, da sette README di sottocartella e da `AGENT_CONTEXT.md`,
il terzo dalla riga S37 dell'audit S01–S40), e le righe S14 e S37 chiedono di non
modificarli.
