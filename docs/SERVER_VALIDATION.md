# Registro delle verifiche prioritarie

Aggiornato il 12 ottobre 2026. Baseline del server: `68f1125` su main.
Questo registro distingue riscontri della sessione di installazione, preparazione
nel repository e prove ancora da eseguire. Non abbiamo una sessione SSH dal
workspace di sviluppo al server: gli esiti reali vanno raccolti dal suo terminale.
La Home usa gli stessi ID in `frontend/src/services/connections.ts`.

## Percorsi e accessi

| Risorsa | Percorso o accesso | Evidenza / limite |
|---|---|---|
| Server Debian 13 | `ServerAle`, utente `ale`, `ssh ale@serverale` | Sessione di installazione dell'utente |
| Checkout Cora | `/srv/cora-server-test` | Non indica necessariamente il codice attivo dopo una release |
| Compose, in ordine | `compose.yml`, `compose.server-test.yml`, `compose.files.yml` | Terzo file locale: contenuto non ancora esaminato; conservarlo |
| Stato persistente | `/srv/cora-server-test/state` → API `/state`, lettura/scrittura | Inventario reale 11/10, allineato allo stato updater |
| NAS | `/srv/nas/Dati/drive` → `/nas/drive`, lettura/scrittura | Mount rilevato; doctor storage superato |
| File del sistema host | `/` → API `/host`, sola lettura | Rilevato nell'inventario; collaudo policy/accessi separato FILE-04 |
| Workspace Programmatore | API `/state/programmer`; host `/srv/cora-server-test/state/programmer` | Allineamento e scrivibilità confermati |
| Updater | `/srv/cora-tools/updater` | Servizio `cora-updater`, codice fidato sotto `installed/updater` |
| Versione attiva registrata | `/srv/cora-tools/updater/current.json` | Confrontare anche gli ID delle immagini in esecuzione |
| Configurazione updater | `config.json`, `compose.json`, `bridge.token` sotto root updater | File privati; non allegare né pubblicare il contenuto |
| Pulsante | `/srv/cora-tools/pulsante-aggiorna` | Servizio `pulsante-aggiorna` |
| Stato pulsante | `/srv/cora-tools/pulsante-aggiorna-state` | Separato dal checkout |
| Cora | `https://serverale.tail7b83c3.ts.net` → localhost `8090` | Accesso dal telefono riscontrato nella sessione |
| Pulsante | `https://serverale.tail7b83c3.ts.net:8443` → localhost `9030` | Tailscale Serve e servizio riscontrati |
| Bridge interno | `http://host.docker.internal:9021` | Autenticato con token; non esporlo tramite Tailscale |
| GitHub Cora | `Aleselva12/serveria1`, branch `main` | `git ls-remote` riuscito; deploy key di sola lettura |
| GitHub pulsante | `Aleselva12/pulsante-aggiorna` | Installazione separata dal codice Cora |
| Backup iniziale | `$HOME/cora-backups/prima-updater-<data>` | Sequenza con backup proseguita; checksum e ripristino ancora da attestare |

Tre file Compose sono livelli della stessa configurazione: base, profilo del
server e override locale. Non sono tre server. Ogni comando che usa Compose
deve conservare lo stesso ordine. L'updater congela la configurazione risolta
all'installazione: cambiare un override sul checkout non aggiorna quel contratto.
Il codice dell'updater è installato separatamente e non viene aggiornato dal
pulsante insieme alle immagini di Cora.

## Lavori fatti e da fare

| ID | Stato | Fatto / criterio di chiusura |
|---|---|---|
| REM-01 | Riscontrato | Login da telefono via Tailscale; upload resta FILE-03 |
| DEP-01 | Parziale | Inventario reale: servizi sani, mount/permessi storage, database/pgvector e modelli disponibili; bridge e commit registrato concordi. Restano BKP-01 e PRG-02 |
| DB-01 | Nuovo, da diagnosticare | Recupero PostgreSQL terminato, servizi tornati sani. Checkpointer uscito con codice 2 il 12/10: raccogliere errori completi e causa prima di chiudere l'episodio |
| DEP-02 | Diagnosi completata; aggiornamento da eseguire | Ore 01:14 confermati ID immagini iniziali e correzione Copilot assente. Registro 68f1125 coerente: nuova versione non applicata. Aggiornare tramite pulsante e verificare commit/immagini dopo esito positivo |
| PRG-01 | Check Docker e risposta modello completati; modifica da collaudare | Isolamento Python, riconoscimento del test fallito, TypeScript e build frontend superati sul server. Runner corretto installato nel bridge. Run reale completed in 218,38 s; nessuno strumento nel campione. Restano file creato, test e risposta nel browser |
| PERF-01 | Parziale | Tre campioni diretti Ollama e un run Cora raccolti: 218,38 s, di cui 217,75 s nel modello e 0,17 s in coda. Restano confronto controllato e carico CPU/RAM |
| BKP-01 | Da collaudare | Verificare checksum, poi restore su macchina separata e vuota con prova di dati e sessioni revocate |
| PRG-02 | Da collaudare | Preparare/applicare una nuova release, confrontare commit e immagini, provare recupero in ambiente separato. Apertura del pulsante o aggiornamento senza novità non attestano il ciclo |
| DEP-03 | Correzione preparata, da collaudare | Aggiornamento fermato prima dell'applicazione: test non avviabili per PermissionError su /app/tests. Normalizzazione dei permessi in Dockerfile API; riprovare suite completa tramite pulsante dopo integrazione |
| PRG-03 | Nuovo, da configurare | La deploy key di lettura non può pubblicare branch. Definire credenziale dedicata di scrittura solo se si vuole usare “Pubblica” in Programma; aggiornamenti in lettura restano possibili |
| PRG-04 | Correzione UI riscontrata nella schermata | Copilot sempre scrivibile, prompt conservato e ID run visibile. Controlli Python/frontend disabilitati quando mancano i relativi file; mappa disabilitata senza Graphify. Run ricevuti identificati come check/mappa, nessuna prova modello attestata |
| BKP-02 | Nuovo, da verificare | Il backup Cora copre database e `/state`, non il NAS esterno. Verificare disponibilità e ripristino del backup NAS |
| LIB-01 | Da collaudare | Un documento sintetico in Libreria: ricerca autonoma, fonti corrette, streaming e rispetto dei permessi |
| FILE-03 | Da collaudare | Upload e foto da telefono; separato dal solo login |
| FILE-04 | Nuovo, da collaudare | La radice host è montata su `/host` in sola lettura: verificare radici autorizzate, confini di lettura e accessibilità dei socket host. L'assenza di `/var/run/docker.sock` nell'API non verifica `/host/run/docker.sock` |

## Inventario reale ricevuto il 11 ottobre, ore 20:38 italiane

Rapporto `inspect`, `sampled_at: 2026-10-11T18:38:53.077650+00:00`.
`ok: false` è spiegato dalle sole immagini di check mancanti:
`cora-programmer-checks:local` e `cora-programmer-frontend:local`.
Gli altri requisiti del collector risultano superati.

- API, web e PostgreSQL in esecuzione e `healthy`; updater e pulsante `active`.
- API UID/GID 1000/1000, workspace scrivibile, mount allineato al bridge,
  nessun socket presente nel percorso API `/var/run/docker.sock` verificato.
- Database con pgvector e 2 migrazioni; doctor storage e Ollama superati.
- Tutti i sei ruoli selezionano `qwen3:0.6b`: disponibilità verificata,
  generazione e comportamento del Programmatore ancora da collaudare.
- Audio disabilitato nell'installazione osservata: nessun collaudo Whisper attestato.
- Commit updater e bridge `68f112515a89cb16a26e4365f45b6c1f8fa9eb03`.
  Il registro iniziale non contiene ID immagini; conserviamo quelli effettivi:
  API `sha256:236e7965f7b3635b5926092f9a9478e6419092c579f0a974f906871e1eecffb7`,
  web `sha256:0c96d6f2db318a80f0ed1c09512ae20fea60a78bb0795db97974c520b8e1043c`,
  PostgreSQL `sha256:7b822b0aac60967beb1ea5e576b8602c94c300a157d187f385ae3e0da199b90a`.

Nessun tempo di risposta o ripristino è misurato da questo inventario.

## Collaudo Programmatore ricevuto il 11 ottobre, ore 20:46 italiane

Rapporto `programmer`, `sampled_at: 2026-10-11T18:46:07.667021+00:00`.
Inventario `ok: true`: entrambe le immagini di check sono ora disponibili.
Il risultato complessivo della prova resta negativo per la build frontend.

| Prova | Risultato | Tempo |
|---|---|---|
| Python: isolamento | Superata | 4.278 s |
| Python: fallimento deliberato | Riconosciuto correttamente | 2.916 s |
| TypeScript | Superata | 21.559 s |
| Build frontend | Fallita, log da raccogliere | 21.666 s |

Workspace isolamento/fallimento: `4b785b82-669d-4c43-b47c-c3f4a2989324`.
Workspace frontend: `b28adf9e-ae8b-44da-b463-5d1f6b8a59ba`.
Immagine Python `sha256:ca02087e2df4d04fe85b0478362fae6b7926ba80b47854431dda759aaf473765`;
frontend `sha256:caf7c888bc1dbb93f756897a37990d8b169878fc5030e5a813bd7dd341d134ac`.
Commit attivo, immagini applicative e servizi invariati rispetto all'inventario.
Questi tempi misurano i check Docker e non la latenza di Ollama o della chat.
Nessun timeout segnalato: la build è terminata con `passed: false`.
Il passo successivo è leggere l'ultima voce `frontend_build` del `checks.json`
del workspace frontend. La causa non è ancora attestata dal rapporto ricevuto.

### Diagnosi e correzione della build, ore 20:50

Lo screenshot del log conferma exit code 1: Vite non riesce a creare
`/tmp/project/node_modules/.vite-temp` durante il caricamento della configurazione.
Il runner collegava tutta `node_modules` alla directory delle dipendenze
fidate in sola lettura nell'immagine. La correzione crea una directory
`node_modules` propria nel tmpfs e collega individualmente le dipendenze
all'immagine; `.vite` e `.vite-temp` restano locali alla prova. Non cambia
rete, UID, mount di sola lettura, capability, limiti o timeout.

Un test di regressione esegue davvero TypeScript e Vite con una configurazione
TypeScript e verifica build e cache separata dalle dipendenze: superato in locale.
Rieseguiti i 15 test updater. La suite `test_programmer_agent.py` non è partita
nel virtualenv di sviluppo perché manca `langchain_core`; non è un fallimento
del collaudo reale Python già superato. Il Docker reale resta da riprovare.

Il bridge host usa `/srv/cora-tools/updater/installed/updater/check_runner.py`:
una nuova release Cora non aggiorna automaticamente quel file. Installare
il solo runner corretto conservando una copia precedente, poi riavviare
`cora-updater` a servizio libero (nessuna release o verifica in corso).
Non rieseguire `updater.setup` e non modificare token, Compose o stato.
Riprovare `frontend_build` nello stesso workspace
`b28adf9e-ae8b-44da-b463-5d1f6b8a59ba`; mantenere la prima prova fallita
nella cronologia. Non ricostruire le immagini di check per questa correzione.

### Correzione installata e build superata, ore 20:57

Lo screenshot ricevuto conferma installazione del solo runner dal commit
`e423fba1197996720c9a342bc48e26cafb442ae8`, copia del file precedente e riavvio
del bridge con `systemctl is-active` → `active`.
Nel workspace frontend originale, nuova prova `frontend_build`:
`passed: true`, `exit_code: 0`, `duration_ms: 30062`.
Vite 6.4.3 ha compilato 1623 moduli, completando la propria build in 9.62 s.
I 30.062 s comprendono l'intero controllo (TypeScript, Vite e gestione Docker),
non soltanto Vite e non una richiesta al modello.

I quattro check Docker previsti sono ora riscontrati sul server. La prima
build fallita resta nella cronologia, seguita dal nuovo esito positivo.
PRG-01 rimane parziale per la prova reale del Programmatore con Ollama;
PERF-01 rimane aperto fino alla misura del modello e del percorso Cora.

### Ollama diretto, 12 ottobre ore 00:34 italiane

Rapporto `sampled_at: 2026-10-11T22:34:01.204593+00:00`, modello
`qwen3:0.6b`, commit server ancora `68f1125`. Inventario e probe positivi;
hash runner installato `e782e9a0e3ee70936cd8e6c18035f0cfd1d3b06692c9d090ba7b84bcbe27d847`.

| Campione | Totale esterno | Primo token* | Caricamento | Prompt | Generazione | Token generati |
|---|---|---|---|---|---|---|
| 1 | 13.603 s | 8.923 s | 7.388 s | 1.308 s | 4.819 s | 64 |
| 2 | 4.908 s | 0.259 s | 0.001 s | 0.068 s | 4.785 s | 64 |
| 3 | 5.826 s | 0.342 s | 0.002 s | 0.090 s | 5.661 s | 64 |

*Il collector considera sia testo sia ragionamento: non è necessariamente il
primo testo visibile all'utente. Prompt di 25 token per ogni campione.
Tutti terminano con `done_reason: length`: il limite di 64 token è stato
raggiunto, quindi il completamento semantico della risposta non è attestato.
Il primo campione include 7.388 s di caricamento; i successivi lo riducono a
circa 1–2 ms. I tempi sono diretti API-container → Ollama e non misurano il
runtime Cora, la memoria, i tool o la UI. Nessuna diagnosi hardware è ancora
supportata da questi soli dati.

Prossima prova: workspace minimo nuovo (README e cartella tests), richiesta
reale del Programmatore per `sum_numbers.py` e due test unittest. Non usare
il workspace di isolamento che conserva il fallimento deliberato, e non
duplicare l'intera suite del repository per questa prova minima. Registrare
workspace e ID run, esito dei file/check e metriche di Attività senza
pubblicazione/applicazione della bozza.

### Blocco UI e run fallito, 12 ottobre ore 00:51

Workspace minimo creato: `ad47686e-4820-42c0-935f-660d34d6dbda`, titolo
`Collaudo Ollama - somma`, due file iniziali. Lo screenshot successivo mostra
selezione corretta del workspace, zero modifiche e banner generico
“Esecuzione failed”. L'utente segnala che il campo chat non è scrivibile e
che un pulsante genera l'errore. Lo screenshot non identifica quale azione
abbia prodotto il run; non attesta ancora un errore del modello.

Nel codice il textarea era disabilitato per backend offline, nessuna selezione,
run in corso o editor aperto. La correzione consente sempre di preparare un
messaggio, mantiene i controlli sull'invio (anche nel gestore), mostra il motivo
del blocco invio e l'ID run, conserva il prompt su errore senza ripetere richieste.
Tre test UI mirati superati; build TypeScript/Vite riuscita.
Occorre raccogliere kind/stato/error_type e diagnostica sicura dei run della
stessa bozza. Nessuna richiesta viene rieseguita per raccogliere questi dati.

### Diagnostica ricevuta, 12 ottobre ore 00:56

Gli ultimi cinque run della bozza sono uno `programmer_graph` fallito,
tre `programmer_check` falliti con `ValueError`, uno `programmer_check`
completato; nessuno di questi è una richiesta `programmer` al modello.
Run mappa `b29b9ab6-abd1-401e-b12a-a8fde8b395d4`; nessun dettaglio di errore
presente nel campione diagnostico ricevuto. Non attribuire questi errori a Ollama.

La bozza iniziale non contiene `tests/test*.py` o `frontend/tsconfig.json`:
Python test runner e frontend runner rifiutano questi prerequisiti mancanti.
La UI ora disabilita i rispettivi pulsanti e spiega cosa serve; i test Python
si abilitano dopo la creazione di un file di test. La disponibilità Graphify
proviene da `/programmer/status`; senza CLI il pulsante mappa è disabilitato.
La causa precisa del singolo run Graphify non è presente nel rapporto ricevuto.
Quattro test UI mirati passati, inclusa riabilitazione dei check dopo creazione
dei file. Queste correzioni successive alla PR #37 sono nella PR #38;
richiedono integrazione in main e aggiornamento del frontend installato.

### Episodio PostgreSQL, 12 ottobre ore 01:06–01:08

Una nuova lettura diagnostica ha incontrato PostgreSQL in recovery e
`psycopg_pool.PoolTimeout` dopo 10 s. Alle 01:08 l'utente rileva tutti e tre
i container Cora `healthy`, PostgreSQL `running`, `RestartCount: 0`,
`OOMKilled: false`; filesystem principale al 21%, circa 692 GiB disponibili.

I log mostrano shutdown alle 01:03:25, avvio alle 01:05:58, uscita del
checkpointer con codice 2 e reinizializzazione interna. Il recupero termina
alle 01:06:55 (`2026-10-11T23:06:55.717Z`), con database pronto ad accettare
connessioni. Il contatore riavvii Docker non misura i riavvii interni del DB.
Non sono ancora disponibili le righe di errore che spiegano l'uscita del
checkpointer. Lo stato healthy attuale chiude il blocco di disponibilità,
non la diagnosi DB-01. Raccogliere log recenti filtrati per ERROR/PANIC/FATAL,
checkpointer e problemi di file/accesso; confermare `pg_is_in_recovery()`
e versione attiva registrata. Non ripetere aggiornamenti durante la diagnosi.

Alle 01:12 `SELECT pg_is_in_recovery()` restituisce `f`. Il log filtrato
ribadisce recupero concluso, senza spiegazione del checkpointer. Servono le
righe complete del breve intervallo di avvio 23:05:54–23:06:02 UTC.
Il registro updater è ancora `68f112515a89cb16a26e4365f45b6c1f8fa9eb03`,
`updated_at: 2026-10-11T18:04:03.821063Z`, `images: null`: non attesta una
nuova release completata. Questo dato non identifica da solo il codice nei
container, che potrebbe essere stato ricostruito fuori dal bridge. Verificare
immagini API/web e presenza della nuova UI (`copilot-send-status`) prima di
proseguire la prova del modello. Non riallineare il registro a mano.

Alle 01:14 confermati gli stessi ID API/web dell'inventario iniziale:
API `236e7965…`, web `0c96d6f2…`; probe statico “Correzione Copilot assente”.
DEP-02 è quindi chiarito: codice remoto aggiornato, container applicativi
ancora iniziali, registro updater coerente. La nuova release non è attestata;
usare il pulsante per applicare main e registrare esito/versione/immagini.

Il breve log di avvio aggiunge un evento precedente al checkpointer:
`2026-10-11T23:05:58.025Z`, `server process (PID 13) exited with exit code 2`,
seguito da terminazione degli altri processi; checkpointer esce alle
23:05:58.657Z. Non attribuire la causa primaria al solo checkpointer.
DB-01 resta aperto per la causa dell'uscita del processo server; database
attualmente sano e fuori dal recovery. Evitare riavvii aggiuntivi non necessari.

### Aggiornamento dal pulsante, 12 ottobre ore 01:23–01:25

Job `5b607d71-a8d4-4888-a424-d95b86f1d019`, versione richiesta
`15afb22` (main, merge PR #38), fallito in fase `testing`.
Versione attiva ancora `68f1125`. La fase è raggiunta dopo build/inspect delle
immagini candidate e prima dell'applicazione: nessuna nuova versione applicata.
Il log privato attesta che unittest discovery non parte per
`PermissionError: [Errno 13] Permission denied: '/app/tests'`.

L'updater usa umask 0077 e `tarfile.extractall(..., filter='data')`:
le directory estratte possono mantenere 0700. Docker COPY mantiene i modi,
ma assegna i file a root; l'API/test gira come utente Cora. La correzione nel
Dockerfile normalizza lettura/traversal di `/app` con `chmod -R a+rX`,
senza cambiare proprietario, concedere scrittura pubblica, eseguire i test
come root o rimuovere la sola lettura del container di test.

Test locale: riprodotta estrazione con umask 0077 e directory tests 0700;
eseguito il comando di permessi effettivo del Dockerfile, verificati directory
0755, file leggibile senza scrittura per gruppo/altri e proprietario invariato,
poi discovery di una fixture. La verifica Docker non root della suite completa
resta al prossimo aggiornamento: nel workspace non è disponibile Docker e il
cambio UID nel subprocess non è consentito dalla mappatura dell'ambiente.
La correzione non richiede modifiche al servizio updater installato o ai token.

Non assegnare “completato” ai collaudi finché manca il rapporto del server.
Conservare gli esiti con data, commit attivo e immagini. Quando emerge un
problema aggiungere ID, evidenza, prossimo intervento e nuova prova richiesta.

## Primo passo: inventario senza aggiornare il server

Dal terminale del server, come `ale`. Il fetch e `git show` recuperano soltanto
lo strumento; non cambiano checkout, servizi o immagini. Non serve integrare la
PR per eseguire questo primo passo.

```bash
cd /srv/cora-server-test
mkdir -p -m 700 "$HOME/cora-checks"
git fetch git@github.com:Aleselva12/serveria1.git verify/server-priorities
git show FETCH_HEAD:deploy/priority_checks.py > "$HOME/cora-checks/priority_checks.py"
python3 "$HOME/cora-checks/priority_checks.py" inspect \
  --compose-file compose.server-test.yml --compose-file compose.files.yml \
  --output "$HOME/cora-checks/inventario-$(date +%Y%m%d-%H%M%S).json"
```

Lo strumento usa solo Python standard sul server e le dipendenze già presenti
nell'API. Legge health, ID immagini, mount effettivi, UID, disponibilità immagini
check, modello assegnato ai ruoli, doctor e bridge. Confronta commit bridge,
registro updater e immagini registrate quando presenti; confronta il mount
`/state` con `state_root` e verifica accesso workspace. Registra hash del codice
fidato installato per confronti successivi, senza copiarne la configurazione.

Non stampa ambienti Docker, token, password, prompt, risposte o log dei test.
Gli errori sono categorie/codici, non output grezzo. I rapporti nuovi hanno
permessi `0600` e non sovrascrivono file esistenti. Sono appunti privati con
percorsi e identificativi: conservarli sul server, condividere qui il JSON,
non committarli nel repository. Un exit code `1` segnala una verifica incompleta
o fallita: leggere le voci, non reinstallare automaticamente i servizi.

## Programmatore: immagini e collaudo

Prima esaminare l'inventario. I check richiedono le immagini Docker fidate;
costruirle da uno snapshot del commit effettivamente attivo, non da un checkout
che può essere rimasto indietro dopo un aggiornamento. Eseguire senza release o
altre verifiche in corso; questi build consumano CPU/disco e possono scaricare
dipendenze. Le prove successive sono offline.

```bash
cd /srv/cora-server-test
git fetch git@github.com:Aleselva12/serveria1.git main
ACTIVE_COMMIT=$(python3 -c 'import json; print(json.load(open("/srv/cora-tools/updater/current.json"))["commit"])')
CHECK_SOURCE="$HOME/cora-checks/source-$ACTIVE_COMMIT"
git worktree add --detach "$CHECK_SOURCE" "$ACTIVE_COMMIT"
docker build -f "$CHECK_SOURCE/programmer_agent/checks.Dockerfile" \
  -t cora-programmer-checks:local "$CHECK_SOURCE"
docker build -f "$CHECK_SOURCE/programmer_agent/frontend-checks.Dockerfile" \
  -t cora-programmer-frontend:local "$CHECK_SOURCE"
python3 "$HOME/cora-checks/priority_checks.py" programmer \
  --compose-file compose.server-test.yml --compose-file compose.files.yml \
  --output "$HOME/cora-checks/programmatore-$(date +%Y%m%d-%H%M%S).json"
```

Se il worktree esiste già, riutilizzare quello stesso percorso dopo averne
verificato il commit, senza rieseguire `worktree add`. Se il commit non è
disponibile nel checkout, fermarsi e controllare il rapporto; non sostituirlo
con `HEAD`. Se i manifest frontend differiscono dall'immagine di check, il
runner rifiuta la prova: ricostruire dall'esatto snapshot, non forzare il controllo.

La prova crea due workspace nuovi in Programma, senza toccare il codice attivo.
Il primo verifica UID 65534, filesystem root e sorgenti in sola lettura,
capability assenti, no-new-privileges, sola interfaccia loopback, assenza di
socket Docker e variabili Cora/credenziali, scrittura solo nell'area temporanea.
Poi aggiunge un test deliberatamente fallito: `passed: false` con
`expected_pass: false` e `ok: true` è il risultato atteso di quella singola
prova. Il workspace mantiene quel test per permettere la revisione; non è una
bozza da rilasciare. Il secondo snapshot verifica TypeScript e build frontend.
Gli ID dei workspace e i tempi sono nel rapporto; i log restano nei workspace.
Questo verifica il percorso di check, non login HTTP, ragionamento o tool del
modello: tali prove seguono dalla UI.

In Programma creare una bozza dedicata e chiedere: “Aggiungi una funzione che
somma due numeri e un test; lavora solo in questa bozza, esegui la verifica Python
e indicami i file modificati”. Verificare richiesta reale Ollama, diff confinato
alla bozza, check e registro in Attività. Non pubblicare/applicare questa fixture.

## Latenza: stesso modello, due percorsi distinti

Quando Cora è libera da altre richieste:

```bash
python3 "$HOME/cora-checks/priority_checks.py" ollama \
  --compose-file compose.server-test.yml --compose-file compose.files.yml \
  --output "$HOME/cora-checks/ollama-$(date +%Y%m%d-%H%M%S).json"
```

Tre richieste sequenziali al modello effettivo del Programmatore, temperatura 0,
massimo 64 token. Non cambia la selezione e non scarica modelli; può caricare
quello scelto in RAM/VRAM. Non scarica dalla memoria il modello prima del primo
campione: non chiamarlo “a freddo” senza evidenza. Registra tempo al primo token
(anche ragionamento), tempo totale, caricamento, elaborazione del prompt,
generazione e conteggi. `done_reason: length` significa limite raggiunto; non
attesta una risposta utile. Questi tempi non includono la coda e i tool Cora.

Dopo la prova reale in Programma, prendere l'UUID completo del run dalla
profilazione/diagnostica in Attività e usare:

```bash
python3 "$HOME/cora-checks/priority_checks.py" trace --run-id <UUID_COMPLETO> \
  --compose-file compose.server-test.yml --compose-file compose.files.yml \
  --output "$HOME/cora-checks/run-$(date +%Y%m%d-%H%M%S).json"
```

Esporta un solo run, senza conversazione, argomenti tool, risultati o eventi.
Mantiene configurazione effettiva limitata a modello/profilo/target/token/keep-alive,
tempi di coda, contesto, tool e singoli span modello. Tempi Cora in millisecondi;
campi provider `*_duration` della traccia in nanosecondi. Non sommare ingenuamente
span annidati al totale e non chiamare il tempo residuo “rete” senza misura.

| Campione | Modello e commit | Coda | Contesto | Primo token | Modello / tool | Totale |
|---|---|---|---|---|---|---|
| Ollama 1, 2, 3 | Da raccogliere | Non applicabile | Non applicabile | Da raccogliere | Da raccogliere | Da raccogliere |
| Programma reale | Da raccogliere | Da raccogliere | Da raccogliere | Da raccogliere | Da raccogliere | Da raccogliere |

Ripetere almeno tre richieste comparabili dalla UI prima di ottimizzare.
Per LIB-01 usare un documento sintetico con una frase riconoscibile e chiedere
a Cora di trovarla senza selezionare manualmente i tool. Controllare fonti e
permessi; registrare ID del run ed eventuale errore, evitando documenti sensibili.

## Backup e ripristino: prova separata

Il controllo iniziale non ferma Cora:

```bash
cd /srv/cora-server-test
python3 deploy/manage.py verify-backup "$HOME/cora-backups/<CARTELLA_BACKUP>"
```

I checksum attestano integrità, non ripristinabilità. Scegliere il backup
effettivo dopo aver elencato le cartelle; non usare un percorso inventato.
Il NAS esterno non è incluso nell'archivio `/state`.

BKP-01 richiede una seconda macchina/VM vuota: checkout del commit del backup
(correlato alle immagini salvate; `revision` può essere il checkout, non la
release attiva), Docker, directory state vuota e nessun servizio Cora
preesistente. Su quella macchina usare `manage.py init`, configurare il nuovo
`deploy.env`, porta/origine e Ollama, poi `manage.py restore <backup>` e
`manage.py up`. Non copiare gli override NAS o i token updater dell'host attuale.
Ripristinare l'API target corretto, specialmente se il backup include Audio.
Non eseguire `deploy/ci_verify.py` sulla macchina attuale: è una fixture CI che
elimina volumi e state del proprio ambiente.

Chiudere BKP-01 solo dopo health, login proprietario, un dato database noto,
un file noto in `/state`, sessione precedente rifiutata e prova delle funzioni
necessarie. Annotare durata, dimensioni, commit/immagini e checksum prima/dopo.
Per PRG-02 collaudare il recupero delle release nella stessa macchina separata;
sul server operativo confrontare nuova versione attiva, immagini e accesso dopo
l'aggiornamento. La chiave GitHub di sola lettura basta per scaricare main.

## Verifica del lotto nel repository

- 91 test frontend superati; build TypeScript/Vite riuscita.
- 6 test del collector (riservatezza, errore reale, niente sovrascrittura,
  compilazione probe, filtro metriche, niente creazione di directory durante
  l'inventario) e 4 test deploy superati.
- 15 test updater superati, compresi override, commit verificato e recupero.
- Nessun daemon Docker o modello/server reale disponibile nel workspace:
  isolamento reale, tempi, restore e release non sono certificati dai test locali.

## Aggiornamento del 12 ottobre: chiusura delle verifiche

Il proprietario riferisce aggiornamento riuscito e accesso da telefono. Il run
`0f6b614b-dde1-4bab-85fd-795601558e6e` è completed, senza errori: 218,38 s,
99,7% nella chiamata modello. Dettagli e limiti in [PROGRAMMER_REVIEW.md](PROGRAMMER_REVIEW.md).
Le voci precedenti descrivono anche incidenti storici: il riscontro successivo
non certifica da solo commit/immagini attivi o capacità di ripristino.

Ordine operativo:

1. Dopo questo aggiornamento, eseguire inspect e trace con il collector aggiornato.
2. PRG-01: in un workspace di prova chiedere `Crea somma.py con somma(a, b) e
   tests/test_somma.py con un test per 2 + 3 = 5. Esegui python_tests e riporta
   i file modificati e l’esito. Non preparare rilasci.` Verificare file, diff,
   risultato reale del test, risposta visibile e ID run. Un saluto non chiude PRG-01.
3. LIB-01: caricare manualmente in Libreria IA un documento sintetico con
   `Codice collaudo CORA: SELVA-7429`. In una nuova chat con tool automatici chiedere
   `Cerca nella Libreria IA il documento di collaudo CORA e riportane il codice
   e il percorso della fonte.` Annotare ID run, tool realmente usati, fonte e
   risposta visibile. Non includere il codice atteso nella domanda.
4. BKP-01: elencare i backup effettivi, verificare quello scelto con verify-backup;
   preparare il restore solo su macchina/VM separata come indicato sopra.
5. PRG-02: confrontare commit e immagini del servizio dopo aggiornamento; provare
   recupero nell’ambiente separato. GitHub in scrittura resta PRG-03 distinto.

Il collector conserva separatamente esito inventario e probe: il report generale
è positivo soltanto se entrambi passano. La modalità trace converte inoltre i
tempi provider in millisecondi e ricorda che completed non certifica il lavoro.
Non è stata cambiata la selezione del modello o degli strumenti: la causa precisa
della lentezza richiede ancora un confronto controllato.

## Riscontro del 13 ottobre 2026, ore 19:15 italiane

Inventario fornito dall'operatore: ok=true. Commit attivo e bridge concordano su
`d0e2521749893dcc09e8966a16c0353c296948c8`; registered_images_match=true.
API `sha256:eaa05f8d18ba82bde702e656c0e0d828fdce3fae3934fd65e0864479c1f563a1`,
web `sha256:57448a295d5a376865df75685a0d63cab987c6739a477e3081f7e3c38972fc76`.
API/web/PostgreSQL healthy, storage e modelli disponibili, servizi updater attivi,
workspace scrivibile e allineato. Attestato il confronto delle immagini dopo
l'aggiornamento; resta aperta la prova di recupero e ripristino.

La schermata successiva del workspace `Collaudo Ollama - somma` mostra invece
`Esecuzione timed_out`: PRG-01 non superato. Non sono visibili ID run, metriche
o elenco completo delle modifiche. Recuperare l'ultima esecuzione programmer
del workspace prima di ripetere la richiesta: non è ancora noto se il timeout
sia arrivato durante il modello o dopo operazioni su file. Nessun aumento dei
timeout o cambio modello applicato sulla base della sola schermata.

Diagnostica successiva: run `19271097-e61f-41fa-a06c-e8095eeb51a2`,
timed_out a 300,272 s, coda 43,62 ms, prepare 0,96 ms. Una sola chiamata
modello interrotta con RunStopped a 300,102 s, first_token_ms=null. Nessun
nodo strumenti nel campione; la pagina Attività mostra zero operazioni del run.
I tre errori sono lo stesso RunStopped propagato a modello, call_llm e LangGraph.
Il callback controlla la cancellazione prima di registrare il token: il null
non certifica assenza di chunk di ragionamento/tool o di lavoro interno Ollama.
Contesto stimato 2776 token, riserva strumenti 4312: sono stime del budget,
non conteggi effettivi Ollama, assenti perché la chiamata non è terminata.
La pagina Attività mostra inoltre pool PostgreSQL di 2 connessioni, entrambe
occupate e 2 richieste in attesa al momento dello screenshot; dato istantaneo,
non prova che il database abbia causato i cinque minuti di questo run.


## Scadenza opzionale delle esecuzioni

Su richiesta del proprietario, `CORA_RUN_TIMEOUT_SECONDS=0` disattiva la
scadenza temporale complessiva, sia nel runtime sia nel contesto degli strumenti.
Il valore predefinito resta 300; valori positivi mantengono la scadenza.
L'annullamento manuale resta cooperativo. Un lavoro che non termina può occupare
lo slot del modello finché non viene annullato e raggiunge un punto di arresto.
Restano distinti timeout di connessione, limiti dei controlli Docker, limite
ricorsione del grafo e numero massimo di token generati.

Attivazione sul server, solo dopo installazione del codice aggiornato: impostare
`CORA_RUN_TIMEOUT_SECONDS=0` nel file `/srv/cora-server-test/deploy.env` e ricreare
l'API con la procedura di deployment che preserva le immagini della release attiva.
Il vecchio codice interpreta zero come un secondo: non impostarlo prima del deploy.
Verificare nella configurazione della nuova traccia `run_timeout_seconds: 0`.

Riscontro hardware a riposo del 13 ottobre: circa 9,8 GiB disponibili, swap usata
524 KiB, nessuna attività swap nei campioni, CPU inattiva 91-98% negli intervalli.
`ollama` non presente nel PATH della shell host; ciò non indica servizio assente.
Questi campioni non misurano il carico durante l'inferenza fallita.
