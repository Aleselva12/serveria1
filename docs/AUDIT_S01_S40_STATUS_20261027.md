# Serveria1 — tracciamento completo S01–S40

Data: 27/10/2026. Rilievi originati dall'audit del commit `effb7d94`; applicazioni proposte nella PR [#100](https://github.com/Aleselva12/serveria1/pull/100) (`audit/easy-fixes-20261027`, base `aef4cdce`). Questo documento è cumulativo. **Non afferma che la PR sia fusa o distribuita sul Debian.**

Legenda: **Fix + test** = modifica proposta nella PR e regressione scritta, non necessariamente CI verde sull'ultimo SHA; **Escluso** = nessun bug da correggere; **Rischio aperto** = non dichiarato risolto. Documentazione/sonde non attestano l'installazione live. Il registro completo e la prima verifica hanno maggiore dettaglio sulle precondizioni.

| ID | Esito | Azione / motivazione | Evidenza | Restante |
|---|---|---|---|---|
| S01 | Fix + test | Lifespan pulisce startup parziale e shutdown con ExitStack | tests/test_audit_easy_fixes.py | CI sull'HEAD; Debian non collaudato |
| S02 | Fix + test | Start idempotente worker embedding | tests/test_audit_easy_fixes.py | CI sull'HEAD |
| S03 | Corretto nel codice; verifica host aperta | Coda postprocess avviata dal lifespan e drenata dopo i run, prima del pool DB | api.py, core/postprocessing.py | Regressioni in tests/test_shutdown_drain.py; nessuna attestazione di deploy |
| S04 | Fix + test | Summary/transcript/episodio isolati e failure metadata-only | tests/test_audit_easy_fixes.py | CI sull'HEAD |
| S05 | Fix + test | Eccezioni embedding in log tecnico solo tipo | tests/test_audit_easy_fixes.py | CI sull'HEAD |
| S06 | Osservabilità migliorata | Rilievo ombrello: health scan libreria e notifiche S28/S29 | core/library_monitor.py, core/notifications.py | Verifica host non fatta |
| S07 | Contratto verificato / diagnostica opzionale | Probe worker con failure closed, risposta booleana voluta | tests/test_machines_api.py | Se serve distinguere TLS/HTTP/protocollo: nuova UI/endpoint |
| S08 | Fix + test | HTTPError separato da errori connessione | tests/test_monitoring.py | CI sull'HEAD |
| S09 | Fix + test | DB error 500 sanitizzato; input/FK invalidi 422 | tests/test_audit_easy_fixes.py | CI sull'HEAD |
| S10 | Corretto nel codice; verifica host aperta | Runtime.shutdown attende run.done fuori dal lock, incluse finalizzazioni terminali non espulse dalla cronologia | core/runtime.py | Regressioni in tests/test_shutdown_drain.py; test con PostgreSQL usa DB usa-e-getta |
| S11 | Escluso / pulizia | Import apparentemente non usati non sono bug | app.py, api.py, core/logging.py | Lint separato, non rimuovere export compatibilità |
| S12 | Escluso | LOG_FILE legacy/test intenzionale | tests/test_events_observability.py | Non rimuovere |
| S13 | Escluso | Preset PC e Debian distinti per design | .env.example, deploy/deploy.env.example | Nessun allineamento automatico |
| S14 | Escluso | Rapporti audit con SHA storici dichiarati | README.md, docs/README_AUDIT_20261025.md | Nessuna modifica storica |
| S15 | Test aggiunti | Lifecycle idempotenza worker e casi probe | tests/test_audit_easy_fixes.py, tests/test_machines_api.py | Test Debian non effettuato |
| S16 | Test aggiunto | Unicità metodo/percorso su app.routes attive | tests/test_audit_easy_fixes.py | Attendere CI; staticamente nessun doppio endpoint |
| S17 | Escluso / pulizia | Import API potenzialmente unused, nessun guasto provato | core/notifications.py, core/registry.py ecc. | Lint opzionale senza refactor |
| S18 | Fix + test | Updater 503 I/O vs 409 conflitto con messaggi sicuri | tests/test_audit_easy_fixes.py | CI sull'HEAD |
| S19 | Escluso | Doppio upload Libreria IA non esiste | tests/test_file_extras.py | Nessuna modifica |
| S20 | Fix + test | Cleanup non maschera eccezione, originale pubblicato conservato | tests/test_ia_library.py | Test fault injection + CI |
| S21 | Escluso / pulizia | Ulteriori import senza uso diretto, non bug | core/chat_store.py, programmer_agent/checks.py ecc. | Pulizia differita |
| S22 | Fix + test | Programmer OSError -> 503 sanitizzato, ValueError -> 422 | tests/test_audit_easy_fixes.py | CI sull'HEAD |
| S23 | Non bug / qualità | No lint F401 obbligatorio in CI; suite di verifica già presente | .github/workflows/verify.yml | Valutazione lint graduale |
| S24 | Escluso, poi revocato il 2026-11-11 | app.py Streamlit legacy opzionale | app.py | Esclusione revocata dal proprietario: vedi l'aggiornamento 2026-11-11 |
| S25 | Escluso | Catch generici intenzionali fail-closed | core/auth.py, core/project_checks.py | Nessuna modifica |
| S26 | Fix + test | Eventi critici separati da API diagnostica opzionale | frontend/tests/runtimePanel.test.mjs | CI sull'HEAD |
| S27 | Fix + test | Polling indipendente per tutti endpoint | frontend/tests/runtimePanel.test.mjs | CI sull'HEAD |
| S28 | Fix + test | Ultimo tentativo/error_type/worker_alive monitor | tests/test_library_monitor.py | Stato solo processo; niente contenuti file |
| S29 | Fix + test | Notifiche: ultimo ciclo/tipo errore senza payload | tests/test_audit_easy_fixes.py | Stato solo processo; nessun invio di test |
| S30 | Fix + test | Contatori write_failures in pagina Attività | frontend/tests/runtimePanel.test.mjs | CI sull'HEAD |
| S31 | Fix + test | Riepilogo controlli scaduti/incerti | frontend/tests/health_dashboard.test.mjs | CI sull'HEAD |
| S32 | Test aggiunti | Failure injection API indipendenti React | frontend/tests/runtimePanel.test.mjs | CI sull'HEAD |
| S33 | Escluso / evidenza | CI baseline audit 6/6 verde | Actions 40384134963 | Non equivale a Debian |
| S34 | Escluso / design | 9 controlli automatici preflight e 12 E2E manuali distinti | core/project_checks.py, core/health_catalog.py | Nessun falso positivo da correggere |
| S35 | Correzione doc | URL runtime README completi /api/v1 | README.md | CI sull'HEAD |
| S36 | Chiarimento doc / verifica host aperta | Due root updater installabili, host reale sconosciuto | docs/MANAGED_APPS.md | Leggere systemd ExecStart/WorkingDirectory sul Debian |
| S37 | Escluso / storia | roadmap storica separata da status corrente | docs/CONSOLIDAMENTO_20261018.md | Nessuna modifica |
| S38 | Escluso / evidenza | 33 documenti link locali presenti | tranche 4 audit | Nessun broken link locale identificato |
| S39 | Escluso / design | Environment PC/Debian intentionally differentiated | .env.example, deploy/deploy.env.example | Non allineare |
| S40 | Correzione doc / verifica host aperta | Sonda Ollama di deploy usa trasporto proxy-free come API | deploy/README.md | Eseguire sola lettura nel container Debian |

## Criteri di conclusione

- Eseguire e ottenere CI verde **sullo SHA HEAD corrente**, non riciclare un esito di commit precedenti.
- Isolare ogni modifica e non cambiare comportamento agentico, approvazioni, memorie, contratti, struttura del database o permessi.
- **S03 e S10 — aggiornamento 2026-11-03:** arresto coordinato implementato: blocco nuove ammissioni, cancellazione cooperativa, attesa delle finalizzazioni dei run, drain dei lavori postprocess accettati, quindi chiusura del pool. Le regressioni riproducono la chiusura prematura senza le correzioni. Il test PostgreSQL richiede `CORA_RUNTIME_TEST_DATABASE_URL` e il database usa-e-getta della CI; gli altri test usano barriere e connessioni simulate. Nessun timeout arbitrario: un'operazione che non ritorna mantiene l'arresto in attesa. Un kill forzato del processo resta fuori dalla garanzia di drain. Verifica sul server e deploy non eseguiti.
- Restano non verificati su **Debian reale** S36 e S40: verificare con operazioni read-only e senza esporre segreti, poi confermare gli eventuali scostamenti. S07 rimane una lacuna opzionale di granularità diagnostica (health false corretto, causa non dettagliata).
- **Nessuna correzione funzionale da apportare** ai rilievi esclusi: mantenerli nel registro evita il ritorno di falsi positivi.
- **S24 — aggiornamento 2026-11-11:** il proprietario ha **revocato** l'esclusione e ha chiesto la rimozione. `app.py` era l'unica interfaccia Streamlit e nessun lanciatore la avviava: né `Dockerfile`, né `AVVIO.ps1`, né la CI, né i README. È stata rimossa insieme alle voci `streamlit` e `rich` di `requirements-core.txt`; `rich` non aveva più import diretti dopo la rimozione di `search_agent/search_render.py` nella PR #149. `requirements-deploy.lock` **non** è stato rigenerato nella stessa modifica: va rifatto con il comando in `deploy/README.md`, altrimenti l'immagine continua a installare entrambi i pacchetti senza che nessuno li usi. La riga resta a registro come decisione storica, non come vincolo attivo.

### Verifica locale delle correzioni di arresto — 2026-11-03

- Ripresa la correzione della PR #106, commit `e0794ae`, sulla base `5b05657`.
- Aggiunta una regressione deterministica sulla concorrenza fra `Run.stop()` e `_finish()`: il codice originale produce `Invalid run transition cancelling -> cancelling`; il codice corretto completa l'annullamento.
- Il test di recupero dopo errore `pg_dump` isola la validazione della destinazione dal comportamento di riavvio. Un test distinto mantiene la verifica del rifiuto dei backup dentro un checkout Git, anche quando il runner usa una directory temporanea sotto Git.
- Suite backend: 592 test, 522 superati e 70 saltati, nessun errore. `python smoke_check.py`: OK. I test PostgreSQL reale e le dipendenze opzionali mantengono i rispettivi requisiti; nessun collaudo Debian o deploy eseguito.

## Comandi non distruttivi per la futura verifica host

Non incollare output contenenti token, URL private o credenziali nei ticket pubblici.

```sh
# Percorso installazione aggiornamenti: nessun restart/copy/update
sudo systemctl show cora-updater.service -p WorkingDirectory -p ExecStart --no-pager
sudo systemctl cat cora-updater.service
# Controllo Ollama senza generazione: richiede essere nel checkout del deploy
docker compose --env-file deploy.env exec -T api python -c 'from core.ollama_transport import get_ollama_base_url,urlopen; print(urlopen(get_ollama_base_url()+"/api/tags",timeout=5).status)'
```
