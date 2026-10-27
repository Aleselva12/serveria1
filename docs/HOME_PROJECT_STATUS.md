# Home: obiettivi e stato osservato — 25 ottobre 2026

## Quadro corrente

La Home desktop e mobile usano lo stesso componente `ProjectRoadmap` e gli stessi 19 obiettivi in quattro macroclassi:

- M1: decisioni di architettura hardware/software ancora aperte;
- M2: implementazioni presenti da collaudare nella configurazione reale;
- M3: servizi, applicazioni ed estensioni da completare;
- M4: automazioni ancora da progettare/implementare.

La fonte attuale è `docs/project-status.json`. Dopo una modifica eseguire `python deploy/render_roadmap.py`: aggiorna `frontend/src/project-status.generated.json`, incluso anche nelle build Docker del solo frontend. I test controllano che sorgente e copia siano identici, che i gruppi siano validi e che gli obiettivi non siano duplicati.

`docs/roadmap.json`, `17 passi.txt` e la loro copia frontend conservano le 17 decisioni storiche del 18 ottobre: non vengono più mostrati come elenco corrente. La chiusura dell’episodio PostgreSQL e l’esclusione del monitor semantico restano conservate nello storico. Programmatore e nuove capacità di sincronizzazione/gestione file mantengono il rinvio hardware. Non si dichiara completata un’attività sulla sola presenza di codice o pulsanti.


## Estensione M1/M2 — roadmap con controlli periodici (branch di sviluppo)

### M1: architettura desiderata, distinta dall'installazione attuale

La pagina ora mostra quattro nodi: **Debian** (API Cora e applicazioni correnti)
e **desktop RX 6800** (risorsa GPU), entrambi presenti; **laptop worker**
aggiuntivo e **NAS dedicato** sono previsti, non installati né collaudati.
Un nodo presente non implica inferenza GPU realmente provata. I nuovi traguardi
aperti riguardano orchestrazione delle attività sui nodi, confronto con sistemi
operativi/piattaforme AI e strategia dei modelli (Colibrì è un candidato da
valutare, non un modello installato).

### M2: due assi indipendenti

- **Sviluppo**: dichiarazione di repository («In costruzione», ecc.), con
  funzioni mancanti e problemi già noti. Non significa che il prodotto sia rotto.
- **Funzionamento**: rimane **Da verificare** finché non esiste un collaudo
  funzionale del flusso completo, datato e riferito alla versione installata.
- **Ambiente / prerequisiti**: `core/project_checks.py` esegue ogni 300 secondi,
  nel processo API, quattro prove di prerequisiti e un test funzionale sintetico: SELECT 1 su
  PostgreSQL SENZA migrazioni, lettura della cartella IA, disponibilità dichiarata
  del motore Audio e lettura del catalogo Ollama; più una trasformazione Word
  append-only su un DOCX sintetico interamente in memoria. Lo stato «Presente» significa
  soltanto che il prerequisito ha risposto, NON che il programma funziona.

La pagina legge `GET /api/v1/project/checks` ogni 30 secondi quando aperta.
I risultati vengono scartati dalla UI se più vecchi di due intervalli; lo
snapshot è conservato **solo in memoria del processo**, quindi sparisce al
riavvio. In un'installazione con più processi API ogni processo mantiene il
proprio snapshot; non è un registro storico unico né un coordinatore condiviso.
La raccolta non genera email, eventi, file utente, inferenze, restore o modifiche.
Il test Word prova il codice di inserimento sintetico, non il riconoscimento cliente su un documento reale.
Gli errori non restituiscono credenziali o dettagli di connessione.

Sono visibili, separatamente per ogni obiettivo M2, le verifiche end-to-end
ancora necessarie e le mancanze note. Al momento questi campi sono revisionati
dalla repository e non vengono compilati automaticamente da un agente.

**Passi successivi aperti:** realizzare test funzionali sintetici isolati,
registrazione duratura delle prove (data, versione, ambiente, esito), un
meccanismo di schedulazione condiviso in caso di più processi API e un percorso
di validazione esplicita prima di dichiarare «funziona». I test unitari e la
verifica HTTP non equivalgono al collaudo operativo del Debian.


## M1/M2 — decisioni, un solo catalogo e collegamenti tra programmi

La M1 in Home non è più una lista parallela di generiche attività. `docs/project-status.json`
conserva separatamente `architecture.confirmed` (scelte realmente decise, NON tutte
implementate), `architecture.open` (ancora da decidere) e `architecture.missing`
(componenti da realizzare). I nodi Debian/desktop presenti e laptop/NAS futuri sono
rappresentati senza inferire l'effettiva inferenza GPU dai soli collegamenti HTTP.

**Unica dashboard M2:** il riquadro desktop originario «Stato dei servizi»
diventa «Salute del sistema e collaudi». Riutilizza il controllo HTTP già esistente
(`GET /api/v1/system/status`) e un catalogo di test separato:
`core/health_catalog.py` è l'unica fonte delle definizioni/ID, usata da
`core/project_checks.py`, Home, Macchine, pagina Programma e gestione gestionali.
Le viste possono fare letture della stessa API, ma non duplicano l'esecuzione
dei test. La Home mobile mostra le verifiche accanto allo stato dei servizi.

**Storicizzazione**: migrazione aggiuntiva `0007_project_health_results.sql`.
Ogni controllo periodico scrive in PostgreSQL il proprio ID, esito, stadio,
durata, ambiente, eventuale commit esposto dall'installazione e timestamp.
La dashboard legge l'ultimo risultato di ogni ID e un estratto dei risultati recenti;
non perde i risultati vecchi soltanto perché escono dalla finestra degli ultimi
100 eventi. Il runner usa un advisory lock PostgreSQL per evitare cicli identici
concorrenti su più processi API. Se PostgreSQL non è disponibile, le verifiche
possono continuare solo in memoria, **segnalate esplicitamente come non persistenti**.

**Controlli automatici circa ogni 5 minuti**: PostgreSQL SELECT 1, leggibilità
Libreria IA, prerequisiti Audio, elenco modelli Ollama, inserimento Word sintetico
in memoria, nonché controlli di contratti/collegamenti:
- Chat API → grafo supervisor → nodi → tool di delega verso agenti;
- Audio API → proposta → approvazione → engine Word;
- Calendario API → proposte → collegamento Google;
- Assegnazione modelli → registrazione API worker.

Questi controlli strutturali localizzano un collegamento mancante, **non provano
che un agente abbia risposto correttamente**. È stato introdotto anche un test
CI sintetico che percorre il grafo di orchestrazione e chiama un *agente finto*
senza LLM, verificando che la risposta delegata arrivi al chiamante.
I collaudi completi su account e servizi reali restano voci del catalogo con
`automated=false` e stato **Da verificare**, senza avvio automatico:
Google Calendar e duplicati, Audio reale, worker GPU, upload/download file,
Immich, Nextcloud, Magazzino Tele, Preventivi, backup/restore e rollback.

**Limiti e scelte di sicurezza**: i controlli automatici non inseriscono
appuntamenti, inviano email, caricano foto, generano preventivi reali, avviano
modelli, modificano documenti di utenti o ripristinano il database.
Un esito PASS del contratto API non equivale a un PASS end-to-end. Gli esiti
sui dati reali e le prove di integrazione sulle installazioni devono essere
eseguiti separatamente, isolando i dati di test e valutando autorizzazioni.
L'importazione automatica di attestazioni da GitHub Actions/updater non è
ancora collegata: la tabella ha i campi `source`/commit per tale sviluppo ma
non dichiara test CI o deploy non osservati dall'API.

Dopo le modifiche, eseguire `python deploy/render_roadmap.py`, la suite
backend/frontend della PR e un collaudo con PostgreSQL su DB di prova.
La build o la PR verde non certificano la versione Debian installata.

## Correzioni del resto della Home

- Eliminati “cinque priorità” su un elenco di 17 passi, ripetizioni dello stesso backlog e il badge positivo “Riscontrato” applicato a un collaudo ancora da svolgere.
- Raggruppamento apribile da tastiera e adattato allo schermo mobile; riepilogo dinamico di obiettivi e macroclassi.
- Servizi descritti come raggiungibili/non raggiungibili/non verificati. Un controllo HTTP non certifica un flusso end-to-end; nessuna certificazione di operatività aggiunta.
- Sul telefono, assenza di health non trasforma Ollama in “Offline”; i servizi restituiti non vengono duplicati dalle righe di fallback. Le misure assenti restano trattini.
- Aggiorna stato ricarica sia health sia monitoraggio; errori di telemetria e servizi restano indipendenti e le richieste non si sovrappongono sullo stesso canale.
- Unità disco GiB coerenti con la divisione per 1024³; testi generici per dispositivo e nessun nome personale fisso nel saluto desktop.

Le misurazioni sono quelle visibili al processo Cora, eventualmente dentro un container. Il controllo Ollama riguarda il provider locale configurato, non la prova di inferenza dei singoli agenti assegnati al worker.

## Prove e limiti

La revisione si basa su main `a8fb19d6acfdec39c65c6c710e4f7769f9c3db3b` e sul confronto README/codice precedente. Le repository esterne del magazzino/preventivi e l’installazione Debian attiva non sono state ispezionate nuovamente: gli obiettivi ne richiedono la verifica, senza inventarne lo stato.

Verifiche frontend e sincronizzazione dati eseguite sul checkout locale; anteprima browser offline desktop e 390×844. Nessun backend, database, OAuth, modello o servizio reale avviato. La navigazione offline verifica contenuti e disposizione, non i servizi. Nessun merge o deploy.


Risultati: 130 test frontend superati (5 regressioni nuove sulla Home), build TypeScript/Vite riuscita; 3 test backend mirati superati, inclusa la sincronizzazione delle fonti. `git diff --check` superato. Resta il warning preesistente sul bundle oltre 500 kB. Browser offline: nessun overflow orizzontale nei viewport mobile e desktop osservati. CI GitHub della PR da verificare separatamente.


## Aggiornamento roadmap — 26 ottobre 2026

La Home usa **tre lavori prossimi ordinati**, senza eseguirli automaticamente:

1. **Orchestratore (prossimo lavoro)**: disegnare e poi implementare routing fra agenti, scheduler e osservabilità con passaggi correlati. Riutilizzare il supervisor LangGraph, le tracce esistenti e il registro salute; ricostruire il percorso richiesta → routing → agente → tool → macchina/modello → risposta. I test di contratto già presenti controllano i collegamenti, ma non sostituiscono il tracing delle esecuzioni reali.
2. **Aggiornamenti Immich/Nextcloud**: aggiungere al gestore host Debian un ciclo sicuro di verifica versione, backup, conferma, deploy e verifica post-aggiornamento. La pagina salute presenta il link di apertura configurato e identifica l'aggiornamento come **lavoro futuro**, non come un bottone di deploy già funzionante. L'updater Cora attuale e il gestore di Magazzino Tele non aggiornano Immich/Nextcloud.
3. **Agente programmatore**: riprendere test e sviluppo con hardware aggiornato. Una pagina volutamente vuota è riservata come `#programmer-next`, senza rimuovere la pagina Programma attuale (`#code`).

### Decisioni di struttura M1

- Debian = nodo operativo, con possibile inferenza futura;
- Desktop e laptop = nodi GPU che hanno già eseguito inferenza secondo le prove dell'utente, senza ancora verificare la corrispondenza fra modello richiesto e realmente eseguito;
- NAS dedicato **futuro** = foto, file, cloud personale e backup, con possibilità di ospitare anche servizi;
- **non è deciso che tutti i database migreranno sul NAS**: valutare di mantenere PostgreSQL e i dati operativi sul Debian e usare il NAS per file e backup, prendendo decisioni servizio per servizio.

La distribuzione software dettagliata, le priorità dello scheduler, la gestione errori e la piattaforma/modelli rimangono **da discutere**, non decisioni già finalizzate.

### Stato M2: conferme utente vs codice e prove

Le voci `goals[].observations` raccolgono conferme operative **riferite dall'utente** (es. trascrizione Audio, calendari manuali e notifiche, aggiornamenti Cora, inferenza desktop/laptop, funzionamento Immich). Non diventano automaticamente prove del commit installato su Debian. La dashboard dei check rimane sorgente unica di evidenza dei controlli automatizzati. I test della pipeline Word, agenti calendario, account Gmail, memoria dopo cambiamenti, identità modello GPU e restore restano aperti.

Per Immich e Nextcloud il backend espone URL di navigazione con `CORA_SERVICE_IMMICH_BROWSER_URL` e `CORA_SERVICE_NEXTCLOUD_BROWSER_URL`. In Home il nome diventa un link solo quando è configurato un URL browser HTTP(S) valido; in assenza del valore non viene indovinato un indirizzo. Per gli aggiornamenti non viene offerta nessuna falsa azione: si mostra solo «lavoro 2», in attesa di un gestore host esplicitamente autorizzato.

Il monitor periodico della salute esiste, con dati PostgreSQL se la migrazione 0007 è presente. Gli obiettivi di miglioramento sono cronologia utile, prove sintetiche isolate e correlazione errori/versioni, senza generare dati nei servizi personali.

**Verifiche necessarie**: test TypeScript/Home, build, verifica aggiornata dei link configurati, collaudo su Debian separato. Non cambiare servizi Immich/Nextcloud o autorizzazioni direttamente con questa modifica.


## Appunti di pianificazione — Orchestratore (27 ottobre 2026)

Questa sezione raccoglie idee e vincoli emersi durante la pianificazione. Non equivale ancora a una specifica definitiva né autorizza modifiche autonome dell'architettura.

### Principi emersi

- **Orchestrazione come ecosistema, non come singolo modello**: valutare una serie di piccoli modelli/componenti specializzati che si completano a vicenda e, insieme, svolgono il ruolo di orchestrazione.
- **Attivazione proporzionata al compito**: una richiesta non deve attivare automaticamente tutta la potenza computazionale disponibile. Il classificatore `simple question` è già un esempio utile di questa direzione.
- **Evitare la sottovalutazione dei task**: il risparmio computazionale non deve portare a classificare come semplice un'attività che richiede più controllo, contesto o verifica. Serviranno test, soglie e meccanismi di escalation.
- **"Larva" / livello di riposo**: valutare un componente molto leggero, attivo quando Cora è a riposo, capace di osservare eventi/stato, contribuire a controlli e diagnostica e decidere quando è necessario attivare livelli superiori.
- **Architettura inizialmente lineare**: prima di permettere circuiti temporanei molto dinamici/adattativi, preferire una gestione più lineare e osservabile. L'adattività più spinta potrà essere introdotta dopo aver raccolto dati e addestrato/validato i modelli.
- **Struttura a livelli ma non necessariamente "più in basso = modello più grande"**: pensare l'orchestrazione come ecosistema di piccoli modelli e componenti eterogenei distribuiti tra i diversi livelli.
- **Trasparenza dell'orchestratore**: ogni decisione rilevante deve essere ricostruibile. L'orchestratore deve lavorare su informazioni corrette e dettagliate e riportare adeguatamente sia i percorsi riusciti sia, soprattutto, errori, fallback e bug.
- **Pagina Attività come registro diagnostico centrale**: deve aiutare sia a localizzare e risolvere problemi, sia a capire dove viene perso tempo e quindi a rendere il sistema più snello e veloce.
- **Context manager da approfondire**: deve distinguere esplicitamente tra registro letterale e registro rielaborato, evitando che i due livelli vengano confusi durante il recupero del contesto.

### Vincoli e argomenti da approfondire separatamente

- **Permission engine e rigidità software**: considerati obbligatori. Devono restare un livello di controllo separato dall'orchestrazione intelligente. Argomento da affrontare in una conversazione dedicata e richiamare quando necessario.
- **Macchine e worker**: l'obiettivo futuro è poter usare la potenza computazionale di tutti i nodi quando desiderato, ma per ora evitare controllo completo delle periferiche da parte dell'IA. Gestione iniziale tramite scelta esplicita dell'utente oppure regole semplici e verificabili, da definire insieme al permission engine.
- **Context manager**: da discutere a breve, inclusi selezione del contesto, registro letterale/rielaborato e criteri di escalation.
- **Event bus**: da discutere e, se confermato, progettare/implementare.
- **Runtime state**: da discutere e, se confermato, progettare/implementare.
- **State machine**: da discutere e, se confermato, progettare/implementare.
- **Mente saggia / Custode**: da mantenere tra gli agenti/ruoli concettuali da approfondire; non assumere ancora che coincida con l'orchestratore.
- **Circuiti temporanei adattivi**: idea valida da conservare, ma da rinviare a una fase successiva rispetto a una prima orchestrazione lineare e verificabile.

### Coda utile per i prossimi passi

1. Ricostruire dalle conversazioni precedenti tutte le idee sull'orchestratore non presenti in questa sintesi.
2. Definire responsabilità precise dell'orchestratore: cosa percepisce, cosa decide, cosa delega e cosa non gli appartiene.
3. Disegnare una prima pipeline lineare e osservabile, con escalation progressiva della capacità computazionale.
4. Definire il ruolo dei piccoli modelli/componenti specializzati nell'orchestrazione e quali decisioni restano deterministiche.
5. Progettare il livello "larva" con particolare attenzione a falsi negativi/sottovalutazione dei task.
6. Collegare ogni decisione dell'orchestratore a tracciamento e diagnostica nella pagina Attività.
7. Aprire approfondimenti dedicati su permission engine/regole software e context manager.
8. Valutare successivamente event bus, runtime state, state machine, Mente saggia e circuiti temporanei adattivi.
