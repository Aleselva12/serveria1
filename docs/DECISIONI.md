# Decisioni in vigore

Registro corrente delle decisioni del proprietario e delle scelte progettuali che
vincolano il lavoro su Cora. Ogni voce cita il documento d'origine, che resta la
fonte con il contesto completo. Prima di rimuovere, archiviare o "correggere"
qualcosa, controllare qui e nell'audit S01–S40: molte voci esistono proprio per
evitare che un falso positivo ritorni.

Una decisione si cambia solo con una scelta esplicita del proprietario; aggiornare
allora questa pagina e il documento d'origine nella stessa modifica.

## Prodotto e architettura

| Decisione | Origine |
| --- | --- |
| Roadmap **solo bidimensionale**: grafica 3D esclusa dal proprietario il 4 novembre 2026; non riaprire autonomamente il progetto Three.js. | `ROADMAP_V2_IMPLEMENTATION.md`, "Parti deliberatamente lasciate a una tranche separata" |
| Rami, stelle, pianeti, lune, collegamenti e architettura della Roadmap li modifica **solo il proprietario**; niente editor IA automatico né `localStorage` come secondo database della pianta. | `ROADMAP_V2_IMPLEMENTATION.md`, stessa sezione |
| Assegnazione di macchine e worker: la **scelta manuale resta autorevole** finché non viene progettata la policy risorse. | `GROUP_B_STATUS.md`, "B4 — Risorse e scheduling", "Decisione corrente" |
| **Non è deciso** che tutti i database migrino sul NAS: valutare servizio per servizio. Debian nodo operativo; desktop e laptop nodi GPU; NAS dedicato futuro per foto, file, cloud e backup. | `HOME_PROJECT_STATUS.md`, "Decisioni di struttura M1" |
| Il permission engine resta un livello di controllo **separato** dall'orchestrazione intelligente; nessun controllo completo delle periferiche da parte dell'IA. | `HOME_PROJECT_STATUS.md`, "Vincoli e argomenti da approfondire separatamente" |
| Libreria IA (FILE-01): solo la Libreria IA, in **sola lettura**, ricerca per nome e contenuto; nessun accesso nuovo al File Server, nessuna scrittura, nessun processo autonomo in background. | `PROJECT_WORK.md`, "FILE-01" |
| Memoria e contesto restano **selettivi** (memoria su richiesta) fino a una decisione esplicita, presa con esempi delle informazioni che devono essere sempre disponibili e con misure comparative. La divergenza rispetto alle descrizioni rilevata dall'audit non prova che la scelta sia sbagliata. | `PROJECT_WORK.md`, "Come dividere il lavoro" e "Decisioni conservate" |
| Una "Decisione da prendere" non va trasformata automaticamente in un bug. | `PROJECT_WORK.md`, "Come dividere il lavoro" |
| I programmi non IA non aspettano che tutte le funzioni siano costruite: il punto di passaggio è avere stabili accesso, dati, backup e manutenzione, più i flussi quotidiani scelti dall'utente. | `PROJECT_WORK.md`, "Decisioni conservate" |

## Codice e manutenzione

| Decisione | Origine |
| --- | --- |
| Gli import apparentemente inutilizzati non sono bug; **non rimuovere gli export di compatibilità**. | `AUDIT_S01_S40_STATUS_20261027.md`, S11, S17, S21 |
| `LOG_FILE` legacy/test è intenzionale. | Audit, S12 |
| Preset PC e Debian distinti per design (`.env.example`, `deploy/deploy.env.example`): non allinearli. | Audit, S13 e S39 |
| I catch generici fail-closed di `core/auth.py` e `core/verify/project_checks.py` sono intenzionali. | Audit, S25 |
| I rapporti di audit con SHA storici non si modificano. | Audit, S14 e S37 |
| Gli import differiti dentro le funzioni (302) tengono aciclico il grafo dei moduli: per questo `E402` è ignorato in `pyproject.toml`. | `pyproject.toml` |
| Righe compatte e più istruzioni per riga sono lo stile del progetto: `E501`, `E701`, `E702` ignorati. | `pyproject.toml` |

## CI

| Decisione | Origine |
| --- | --- |
| `age` è **opzionale** nel job `verify` (il test dei backup ha `skipUnless` e salta da solo) e **obbligatorio** nel job `deployment`, dove `deploy/ci_disposable_deployment.py` chiama `updater.ci_release_rollback.verify`, che esegue `age-keygen` con `check=True`. Non invertire l'asimmetria. | PR #151, `.github/workflows/verify.yml`, `deploy/ci_disposable_deployment.py` e `updater/ci_release_rollback.py` |
