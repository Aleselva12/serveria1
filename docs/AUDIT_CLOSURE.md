# Riscontro dell’audit — 10 ottobre 2026

Audit originale: main `882ed5f963d0be99a4749b9317b04a869b3c0aae`.
Le correzioni qui elencate sono implementate nel codice; questo documento non
attesta installazione, merge o prove sul server personale.

| Punto PDF | Correzione | Riferimento |
|---|---|---|
| 1 | Modelli degli specialisti risolti a ogni chiamata | core/models.py e grafi specialisti; test_runtime_models.py |
| 2 | Impostazioni in /state, scrittura atomica; errore di salvataggio distinto dal provider e nessuna seconda lettura dopo il salvataggio | compose.yml, core/models.py, api.py |
| 3 | Profilo server esplicito nel deployment base | compose.yml |
| 4 | Override mantenuti da gestione deploy e installazione updater, nello stesso ordine | deploy/manage.py, updater/setup.py |
| 5 | UI descrive il contesto proprietario come consultazione selettiva | frontend/src/App.tsx |
| 6 | README allineato alla memoria su richiesta; nessuna reintroduzione del recupero sempre attivo | README.md |
| 7 | Dettagli provider ammessi nella proiezione persistente e nella vista runtime | core/observability.py, core/execution_traces.py |
| 8 | Solo categorie e messaggi fissi del provider, anche per la lettura dei vecchi archivi | core/provider_errors.py, test_provider_errors.py |
| 9 | Endpoint unico 11434, trasporto senza proxy ambiente per probe/embedding, doctor include Programmatore | core/ollama_transport.py, deploy/doctor.py |
| 10 | NAS soltanto nell’override, porta guida 8090, profilo di collaudo distinto da garanzia di produzione | deploy/README.md, deploy/SERVER_TEST_CURRENT.md |
| 11 | Profili Docker via bridge host autenticato, snapshot verificato fuori dal mount API, comandi fissi e limiti; API senza socket Docker | updater/check_runner.py, updater/engine.py, programmer_agent/checks.py |
| 12 | Link nuovi aprono la UI, richiedono login e conservano la destinazione interna; token nel frammento URL | AuthGate.tsx, SharedFile.tsx, sharedFiles.ts |
| 13 | Nginx sovrascrive X-Forwarded-For; API accetta un solo IP e soltanto dal peer configurato, Uvicorn non riscrive il peer | deploy/nginx.conf, core/auth.py, Dockerfile |
| 14 | source-map-js aggiornato a 1.2.2, senza aggiornamenti indiscriminati | frontend/package-lock.json |

Le correzioni Programmatore della PR #33 erano state integrate nel branch
`feat/library-approved-writes`, non in main: questo lotto le riporta insieme
alla diagnostica della PR #34. Il confronto è con il codice, non soltanto con
l’etichetta “merged” della PR.

## Verifiche e limiti

Verifica finale Linux: 280 test backend, 223 passati e 57 saltati; 90 test
frontend passati e build TypeScript/Vite riuscita. npm ci con il lock aggiornato
e npm audit completati (zero vulnerabilità segnalate). Le prove del
bridge verificano HTTP, autenticazione, impronta, copia isolata e rifiuto di
profili/percorso non consentiti; il daemon Docker e Ollama non sono disponibili
qui. Le integrazioni PostgreSQL e gli altri test con prerequisiti mancanti sono
saltati e non conteggiati come passati. Il controllo dipendenze npm non segnala
vulnerabilità alla data di questa verifica.

I test Windows con symlink segnalano l’assenza dei privilegi necessari; i test
specifici Debian sono marcati POSIX. La correzione winerror 206 è provata con
un errore simulato. Una vera esecuzione Windows resta da fare.

I vecchi link che puntano direttamente all’API restano validi per una sessione
attiva; ricreare il collegamento dalla UI per ottenere il percorso con login.
Il download verifica ancora sessione, scadenza, revoca e versione del file.
Nessuna condivisione pubblica o multiutente è stata introdotta.

## Checklist unica del server

- [ ] Registrare commit installato, file Compose in ordine, UID/GID e percorsi
  state/NAS. Ricostruire API e web; verificare login e avvio PostgreSQL.
- [ ] Cambiare modello, chiamare Supervisor e uno specialista, ricreare API e
  verificare selezione persistente. Confrontare doctor, salute e modello effettivo.
- [ ] Eseguire lettura/ricerca/copia Libreria con Ollama; provare conferma,
  versione cambiata, cestino e ripristino. Nessuna cancellazione definitiva.
- [ ] Installare/aggiornare il servizio host dal checkout fidato seguendo
  updater/README.md. Conservare token/configurazione/job/backup. Preparare entrambe
  le immagini di verifica, incluse le nuove dipendenze frontend. Provare Python,
  TypeScript, build, fallimento, timeout e pulizia container dal backend Docker.
- [ ] Da telefono su 5G/Tailscale verificare HTTPS, Origin, cookie Secure,
  streaming e riapertura link senza sessione; provare scadenza/revoca del link.
- [ ] Controllare gli IP effettivi di due dispositivi nel percorso di proxy
  reale: cinque login falliti del primo non devono bloccare il secondo. Se c’è
  un proxy prima di Nginx, configurare esplicitamente la catena fidata.
- [ ] Provare foto/upload interrotto e ripreso, permessi filesystem e spazio
  insufficiente con dati di prova.
- [ ] Su installazione sacrificabile verificare preparazione/applicazione
  rilascio e rollback, backup di DB/state e ripristino dopo ricreazione. Non
  eseguire prove distruttive sull’unica copia dei dati personali.

Le estensioni future (OCR, sincronizzazione, automazioni eseguibili, documenti
avanzati) restano nel PROJECT_WORK e nella Home, separate dai difetti dell’audit.
