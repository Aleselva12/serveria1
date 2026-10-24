# Macro-obiettivo 0: test eseguibili e integrazione servizi

Verifica del 24 ottobre 2026 sulla PR Draft #84, branch `audit/consolidation-calendar-docs-20261024`, base esaminata `524294576ec11868509e7b7de49a888a0826636f`.

## Correzioni verificate

- Google Calendar: il recupero dopo timeout confronta titolo, descrizione, inizio, fine e promemoria; rifiuta eventi cancellati e chiavi riutilizzate per payload diversi. Gli istanti equivalenti con offset diversi sono riconosciuti. Prima il confronto delle date mancanti poteva nascondere un cambio di orario; fine, note e promemoria non venivano confrontati.
- Word: una proposta scaduta viene persistita come scaduta prima del nuovo inserimento. Prima l'indice antireplay continuava a bloccare una nuova proposta anche dopo la scadenza mostrata dalla UI.
- Ricerca Word: un DOCX danneggiato viene conteggiato tra i file saltati, senza nascondere i clienti nei documenti validi. Percorsi assoluti e drive vengono rifiutati anche su Windows.
- Frontend Audio: il componente commerciale viene ricreato al cambio registrazione/versione, evitando di riutilizzare selezioni e stato della trascrizione precedente. Il test Audio carica il vero componente commerciale.
- Frontend Calendario: conserva l'errore della scrittura anche quando fallisce la rilettura dello stato persistente.
- Contratto migrazioni: normalizzazione CRLF nel test del baseline, coerente con il migratore; nessuna modifica al baseline o alla migrazione 0006.

## Copertura dei servizi

PostgreSQL 16 + pgvector temporaneo, documenti DOCX e registrazioni sintetici. Nessun mount NAS, account Google reale o modello operativo.

- Installazione completa; upgrade reale da 0001-0005 a 0006 preservando una registrazione; seconda esecuzione del migratore senza riapplicare la migrazione; indice antireplay presente.
- API Audio/Word: autenticazione, ricerca cliente, proposta senza scrittura, approvazione con backup originale, rifiuto, versione audio obsoleta, Word modificato, scadenza, duplicati, esito incerto e divieto di replay.
- Due approvazioni Word concorrenti: una sola pubblicazione e un solo backup.
- Google: proposta persistita, approvazione owner una sola volta, ID di creazione derivato dall'approvazione, blocco dopo cambio account OAuth. Il provider Google e le sue risposte sono simulati.
- Sync Google: ID deterministico, listing obsoleto, timeout dopo insert e riconciliazione senza secondo insert nella stessa chiamata.
- UI commerciale: cliente esplicitamente selezionato, versione audio inviata, proposta senza pubblicazione, pubblicazione solo dopo approvazione.

## GitHub Actions

Esaminati tutti i 90 run presenti per il branch al controllo. Due run falliti sul vecchio commit `522213047810be415c7e1dfcb92adac0ebe02384`:

- [40105859480](https://github.com/Aleselva12/serveria1/actions/runs/40105859480)
- [40105855421](https://github.com/Aleselva12/serveria1/actions/runs/40105855421)

Log dei job `verify`, `deployment (api)` e `deployment (api-audio-cpu)`: `SyntaxError` nel vecchio `tests/test_google_calendar_approvals.py`, doppio backslash a fine riga. I job deployment fallivano quando la preparazione updater eseguiva lo stesso test. La correzione era già presente nella base 5242945 e i test sono stati rieseguiti. Gli ultimi run della base risultavano ancora `queued`, senza log disponibili; i risultati storici verdi non validano il nuovo commit.

## Risultati e limiti

Risultati finali sulla versione corretta: 482 test backend Linux, OK con una sola esclusione (Graphify CLI opzionale non installato); 113 test frontend Linux, tutti superati; compilazione TypeScript/Vite e smoke check superati. Anche i 113 test frontend e la compilazione su Windows sono superati. La prima suite Windows completa ha eseguito 471 test con 5 failure, 6 errori e 33 esclusioni: permessi POSIX, symlink senza privilegi Windows, getuid, semantica degli errori filesystem e formati dei percorsi. Questa esecuzione non è dichiarata verde. La suite Linux completa è stata quindi eseguita anche con Git, Node e dipendenze frontend per coprire i casi POSIX e updater. Il controllo frontend Windows ha superato 113 test e la compilazione TypeScript/Vite; resta l'avviso sul bundle oltre 500 kB.

Questi sono test locali in contenitori e con servizi temporanei, distinti dalla CI e dal collaudo del server Debian reale. Non certificano:

- OAuth e comportamento del servizio Google reale, consenso/scopes e riconnessione;
- trascrizione effettiva Whisper, diarizzazione o qualità dell'analisi Ollama;
- compatibilità con tutti i Word autentici; tabelle/oggetti restano rifiutati;
- permessi, mount, backup/ripristino, Tailscale e concorrenza con editor esterni sul Debian reale;
- build delle immagini deployment api/audio nell'ambiente GitHub per il nuovo commit.

La pubblicazione Word protegge con hash e lock interno, ma un editor esterno non rispetta quel lock: il controllo hash prima di os.replace non costituisce una transazione filesystem con software esterno. Serve collaudo su copie e coordinamento delle scritture. Nessun duplicato storico Google viene cancellato automaticamente.

Nessun merge, deploy, modifica a main, accesso al server Debian o uso di dati reali.
