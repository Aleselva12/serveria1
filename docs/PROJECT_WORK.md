# Piano di consolidamento del server

Aggiornamento: 10 ottobre 2026. Baseline esaminata: main, commit 882ed5f.
Questo è il primo inventario operativo derivato dall'audit e dai promemoria sparsi.
La revisione continua durante gli interventi: non è una certificazione di ogni
percorso né del server installato.

La lista visualizzata dalla Home è in
[connections.ts](../frontend/src/services/connections.ts).
Le verifiche prioritarie hanno ID e stato. Le tabelle storiche sotto sono una
fotografia del primo lotto; il registro corrente dei collaudi e dei percorsi è
[SERVER_VALIDATION.md](SERVER_VALIDATION.md), aggiornato all'11 ottobre 2026.

## Come dividere il lavoro

1. **Consolidamento:** deploy, persistenza, override, backup, modello effettivo,
   diagnostica e test. Interventi piccoli, verificabili e separati.
2. **Utilità quotidiana:** telefono/Tailscale, file, foto, upload e condivisione.
   Il collaudo richiede la macchina reale.
3. **Funzioni:** completare prima le letture agentiche dei file, poi le scritture
   con policy; verifiche del Programmatore; automazioni costruite per fasi.
4. **Efficienza:** misurare prima di modificare il contesto o i modelli.
   Le scelte recenti di memoria su richiesta restano valide fino a una decisione
   esplicita; correggere le promesse dell'interfaccia è distinto dal ripristinare
   il comportamento precedente.
5. **Programmi remoti non IA:** fase successiva. Partire da attività concrete,
   dispositivi, dati, risorse disponibili e necessità di backup. Scegliere e
   collaudare un servizio per volta, con accesso Tailscale.

Per ogni lotto: leggere il percorso UI → API → dominio → persistenza/servizio;
ricontrollare documentazione e promemoria; implementare; eseguire verifiche
pertinenti; registrare cosa richiede ancora il server reale. Nuovi difetti
entrano nella lista prima di estendere lo scopo del lotto.

“Preparato in locale” significa codice scritto e controllato, non installato.
“Da collaudare” richiede prove dell'ambiente finale.
“Decisione da prendere” non va convertito automaticamente in un bug.
Le attività rinviate non impediscono di usare il server per i casi d'uso concordati.

## Attività aperte (collaudi e funzioni future fuori dalla chiusura audit)

### Utilità quotidiana

| ID | Lavoro | Priorità | Tipo | Stato |
|---|---|---|---|---|
| REM-01 | Telefono tramite Tailscale | P1 | Collaudo | Accesso riscontrato; upload resta FILE-03 |
| BKP-01 | Ripristino completo su ambiente sacrificabile | P1 | Collaudo | Da collaudare |
| FILE-03 | Upload e foto da telefono | P2 | Collaudo | Da collaudare |
| EXT-01 | Programmi remoti non IA | P3 | Decisione | Successivamente |

### Funzioni

| ID | Lavoro | Priorità | Tipo | Stato |
|---|---|---|---|---|
| PRG-01 | Bridge verifiche Programmatore, immagini e isolamento | P2 | Collaudo | Da collaudare |
| PRG-02 | Ciclo release e recupero | P2 | Collaudo | Da collaudare |
| FILE-02 | Estensioni residue: cartelle, importazione e ripristino agentico | P2 | Funzione | Da fare |
| SYNC-01 | Originali e copie IA | P3 | Decisione | Decisione da prendere |
| AUTO-01 | Esecutore delle automazioni grafiche | P3 | Funzione | Da fare |
| OCR-01 | Leggere PDF scansionati | P3 | Funzione | Da fare |
| AUD-01 | Audio locale e diarizzazione opzionale | P3 | Collaudo | Da collaudare |
| MAIL-01 | Gmail e preventivi | P3 | Collaudo | Da collaudare |
| FUT-01 | Obiettivi avanzati | P3 | Decisione | Rinviato |

### Efficienza

| ID | Lavoro | Priorità | Tipo | Stato |
|---|---|---|---|---|
| PERF-01 | Misurare la latenza prima di ottimizzare | P2 | Collaudo | Da collaudare |

## Primo lotto preparato

- Compose server esplicito e impostazioni del modello in /state.
- Radice NAS soltanto nell'override che effettivamente la monta.
- Gestore deploy con --compose-file ripetibile, usato anche al riavvio del backup.
- Guida coerente con la porta 8090 e istruzioni per installazioni già inizializzate.
- Home con inventario per utilità/funzioni/efficienza e criteri di completamento.
- Test del mantenimento degli override lungo il backup simulato.
- Il test dei permessi Unix viene esplicitamente saltato su Windows.

Verifiche locali: 86 test frontend passati, build TypeScript/Vite riuscita;
tre test deploy passati e uno Unix saltato. Il ciclo Docker/NAS e il ripristino
reale restano da collaudare: il daemon Docker Linux non è disponibile qui.
Le modifiche restano sul branch locale fix/deploy-and-project-backlog;
nessun aggiornamento del server o di main.

## Decisioni conservate

Memoria e contesto sono ora selettivi per contenere il costo dei prompt.
L'audit ha rilevato una divergenza rispetto alle descrizioni, ma non prova che
la scelta sia sbagliata. Per decidere il comportamento finale servono esempi
delle informazioni che devono essere sempre disponibili e misure comparative.

La roadmap non implica che tutte le funzioni vadano costruite prima di
aggiungere programmi non IA: il punto di passaggio è avere stabili accesso,
dati, backup e manutenzione, più i flussi quotidiani scelti dall'utente.


## Lotto base — continuazione del 10 ottobre 2026

Branch `fix/base-deploy-runtime-models`, derivato da main `882ed5f`.
Il ramo locale citato nel primo lotto non era disponibile in questo ambiente e
non risulta tra i rami remoti: le correzioni seguenti sono state ricostruite sul
codice main. L'inventario Home `project-work.json` citato sopra non è presente in
questa baseline; il primo inventario resta una fotografia del lavoro precedente,
non una dichiarazione di implementazione su questo ramo.

- DEP-01: Compose in modalità server, selezione modello in `/state`.
- DEP-02: `manage.py --compose-file` ripetibile mantiene gli override anche al
  riavvio dopo il backup; NAS dichiarato nell'override che lo monta.
- MOD-01: research, audio, email, structure e programmer risolvono il modello a
  ogni chiamata come il supervisor; non conservano la selezione dell'import.
  Le chiamate già in corso non vengono interrotte.
- Salvataggio impostazioni atomico; JSON non-oggetto trattato come configurazione
  assente; selezioni non installate respinte senza cambiare quella precedente.
- Guide deploy aggiornate: porta 8090, manutenzione con override e migrazione
  delle installazioni già inizializzate.

Verifica locale: 4 test deploy, 4 test runtime model (inclusi tutti i cinque
specialisti), 3 test grafo superati. Inferenza simulata nei test; nessuna prova
su Ollama reale, Docker, NAS, telefono o ripristino completo. Nessun deploy o
merge su main. OBS-01, FILE-01 e gli altri lotti restano aperti.

## FILE-01 — Libreria IA in sola lettura

Decisione utente: soltanto la Libreria IA, ricerca per nome e contenuto,
consultazione anche senza invito esplicito se pertinente alla richiesta.
I tre tool `library_list`, `library_search`, `library_read` sono disponibili in
modalità automatica; una selezione manuale li può escludere. Nessun nuovo accesso
al File Server, nessuna scrittura e nessun processo autonomo in background.

La chat mostra query, cartella e tentativi di lettura nel flusso autenticato.
Il pannello è transitorio (ultimi 200 passaggi, ultima richiesta della sessione),
non uno storico persistente: può perdere eventi se il bus esaurisce il buffer.
Query e percorsi di questo evento non entrano nell'archivio diagnostico.

Controlli circostanti: traversal e symlink respinti, directory non disponibile
distinta da zero risultati, documenti corrotti conteggiati come non leggibili,
cancellazione/timeout propagati. Limiti esistenti di byte, caratteri e pagine
restano attivi; la scansione si ferma con errore oltre 2000 file.
I reader non costituiscono una sandbox per parser di documenti ostili; come gli
altri accessi filesystem del progetto, non escludono race con writer esterni.

Home aggiornata con collaudo Ollama/server e promemoria su storico privato,
indicizzazione e OCR. Scritture, sincronizzazione, accesso server e OCR restano
lotti distinti. `python-dotenv` era già in requirements-test.txt: era assente
nell'ambiente di test ripristinato, non nel manifesto delle dipendenze.

Verifiche di questo lotto: 26 test backend mirati (8 Libreria IA, 4 selezione
tool, 6 inventario, 8 context pages), 87 test frontend, build TypeScript/Vite e
smoke check superati. Dipendenze backend ripristinate in un virtualenv dedicato.
Da collaudare sul server con Ollama reale; nessun deploy eseguito.


## FILE-02 — copie, modifiche e cestino controllati

Decisioni: copie libere soltanto all’interno della Libreria IA, modifica e
spostamento nel cestino dopo conferma, nessuna eliminazione definitiva.

Implementati tool di copia con nome libero e pubblicazione esclusiva, metadati
SHA256, sostituzione puntuale di testo UTF-8 e cestino compatibile con la pagina
File. Conferma tramite il flusso esistente in Attività, con parametri esatti e
controllo della versione prima dell’effetto. La versione precedente alle modifiche
viene conservata nel cestino. Il ripristino manuale richiede percorso libero.

Controlli circostanti: il vecchio append Word era automatico; ora richiede
conferma e SHA256, conserva la versione precedente e pubblica atomicamente.
La creazione Word non può più sovrascrivere un file comparso dopo il controllo.
Nessun nuovo accesso a originali o File Server. Copie limitate alla dimensione
configurata; modifica strutturale PDF/Word, cartelle, importazioni esterne e
ripristino agentico restano futuri e sono riportati nella Home.

Le policy sono configurabili dal proprietario in Attività: i default di questo
lotto sono copia automatica, modifica/cestino con conferma. Nessun deploy.
Come i percorsi preesistenti, i lock serializzano gli accessi in processo ma non
impediscono race da writer esterni al servizio.

Verifiche del lotto FILE-02: 34 test backend mirati (9 scritture, 8 letture,
7 contratti, 4 chat tool, 6 inventario), 87 test frontend, build TypeScript/Vite,
smoke check e diff check riusciti. Proposte/permessi testati con persistenza
simulata; il ciclo di approvazione PostgreSQL e il collaudo con Ollama/server
reale restano da verificare nell'ambiente finale.

## OBS-01 — diagnostica provider riservata

Implementata classificazione di errori Ollama e trasporto in messaggi fissi,
limitati ai passaggi modello. Nessun testo grezzo di eccezioni, URL o risposta
provider viene conservato come error_detail. Messaggi non riconosciuti restano
generici. Il filtro dell’archivio conserva soltanto i messaggi ammessi, e la
vista tracce li mostra. Anche letture di vecchi export JSONL filtrano i dettagli
non ammessi; i vecchi file non vengono riscritti o eliminati.

OBS-01 rimosso dalla tabella dei lavori aperti; resta il collaudo su Ollama e
PostgreSQL reali. Nessun deploy. Il selettore modello e gli altri percorsi API
non sono modificati da questo lotto.

Verifiche OBS-01: 17 test backend mirati passati, 8 integrazioni PostgreSQL
saltate senza DB; 87 test frontend e build passati. Controllati callback, bus,
filtro archivio, payload SQL simulato, lettura della vista e rendering UI.

## Pulizia attività e verifiche Programmatore

DEP-01, DEP-02, MOD-01 e FILE-01 rimossi dalla tabella del lavoro aperto; FILE-02 conserva solo
le estensioni non implementate. Lo storico dei lotti resta sopra. Il catalogo
riconosce il tool del cestino della Libreria e la Home distingue funzioni fatte
ed estensioni residue. I collaudi server restano aperti.

Programmatore: sintassi senza file applicabili non più attestata come successo;
interruzioni registrate come verifica non completata; controllo dell'impronta
prima/dopo la verifica per non attribuire un successo a sorgenti diversi.
Test Python in copia temporanea nel container, con mount originale read-only,
rete disabilitata e limiti invariati salvo spazio temporaneo portato a 256 MB.
Docker reale e installazione server rimangono da collaudare (PRG-01).

Verifiche di questo intervento: 22 test Programmatore passati e uno Graphify
opzionale saltato, 6 test inventario passati; 87 test frontend e build riusciti.
Test Docker simulati: non attestano daemon, immagini o deploy reali.


## Chiusura delle correzioni dell’audit del 10 ottobre

I 14 rilievi sono riconciliati in [AUDIT_CLOSURE.md](AUDIT_CLOSURE.md), con
riferimenti al codice e un’unica checklist dell’ambiente reale. Le voci concluse
sono rimosse dal lavoro aperto, conservando lo storico. La memoria rimane
selettiva: questa scelta è confermata, non una decisione ancora sospesa.

Corretti endpoint/trasporto Ollama, distinzione errori filesystem, link condivisi
attraverso il login, identità del client dal solo proxy fidato e source-map-js
1.2.2. Il bridge host ora esegue i controlli del workspace su copia verificata;
la sua installazione conserva tutti gli override Compose. Documentazione e Home
sono allineate. I test con link simbolici indicano il prerequisito Windows
quando manca; il test UID/GID Debian è esplicitamente POSIX. Il caso percorso
troppo lungo Windows è mappato a 400.

Il branch riporta anche le correzioni Programmatore della PR #33, confluite
soltanto nel precedente branch Libreria e non in main, e la diagnostica della
PR #34. Nessun merge o deploy eseguito durante questo lotto.

L’esecuzione delle automazioni, OCR, sincronizzazione e gestione agentica
avanzata dei documenti restano estensioni future: non sono bug residui dei
14 rilievi. I collaudi richiedono server, modelli e dati di prova reali.

Verifica finale: 223 test backend passati, 57 saltati per prerequisiti; 90 test
frontend passati, build riuscita e npm audit senza vulnerabilità segnalate.


## 13 ottobre — generazione senza scadenza e controlli nelle chat

Implementati in repository: politica di generazione senza scadenza o tetto di
output, compatibile con deploy.env precedente; timer locale e annullamento nelle
due viste; scelta corta/media/lunga come istruzione, con API validate. La finestra
di contesto rimane finita e distinta dal tetto di generazione.

Da fare sul server: installare la PR, controllare configurazione effettiva,
completare il compito somma.py + test, misurare attesa e cancellazione. La
cancellazione resta cooperativa, da rafforzare nel trasporto per interrompere una
lettura Ollama bloccata senza aspettare il prossimo chunk. Non attestiamo ancora
PRG-01 o PERF-01 completati. Restano LIB-01 e prove backup/ripristino separate.

Verifica locale del lotto: 95 test frontend e build riusciti; 12 test runtime,
4 test politica di generazione, 4 test modelli e 22 test Programmatore superati;
un test Graphify saltato per prerequisito opzionale. Nessun collaudo live implicito.

### Correzione del blocco aggiornamento dopo PR #41

Il test `test_effective_profile_is_non_secret_and_role_aware` pretendeva ancora
512 token con la nuova modalità illimitata predefinita (-1). Riprodotto l'unico
fallimento della suite completa; identico nei job GitHub verify e deployment
api/api-audio-cpu. L'updater sul server mostra failed/testing e versione attiva
d0e2521: coerente con lo stesso test, ma il log del job host non è stato acquisito.

Il test ora sceglie esplicitamente la modalità con limiti; un secondo caso verifica
la configurazione illimitata predefinita anche con le vecchie variabili installate.
Nessun controllo di rilascio rimosso e nessun limite reintrodotto. Verifica locale:
307 test raccolti, 250 superati e 57 saltati per prerequisiti; smoke check riuscito.
La precedente verifica mirata non includeva questo test: attendere anche i job
GitHub di deploy prima del prossimo merge. Collaudo server ancora da ripetere.

## 13 ottobre — taratura Qwen3 e thinking visibile

Home/Obiettivi rinviati: aggiunta revisione dei modelli (campionamento, thinking,
quantizzazione, contesto, dense/MoE e valutazione separata del fine-tuning dei pesi).
Profilo Qwen3 applicato centralmente anche ai chiamanti che chiedevano temperatura
zero: temperatura 0.6, top_p 0.95, top_k 20, min_p 0, reasoning esplicito.
L'adattatore passa min_p alle opzioni Ollama: ChatOllama 1.1 non lo espone direttamente.
Nessun timeout di generazione reintrodotto; output illimitato invariato.

Chat/Programma: pannello espandibile del thinking emesso dal modello, distinto
dalla risposta e dagli effetti dei tool. Buffer degli ultimi 24000 caratteri per
chiamata con segnalazione del taglio visivo, resync SSE e dati in memoria soltanto;
nessun thinking nei transcript o nell'archivio diagnostico. Il taglio del buffer
non interrompe la generazione. Cancellazione tuttora cooperativa.

Modello scelto per la prova server: qwen3:8b Q4_K_M (~5.2 GB di download).
`python -m deploy.prepare_qwen3` verifica almeno 8 GiB di RAM disponibile, scarica,
controlla le capacità tools/thinking e prova il caricamento a contesto 8192 prima
di salvare la selezione globale. Il controllo RAM è preliminare, non una garanzia
di prestazioni o assenza di swap. Non eseguito sul server da questa sessione.

Da fare: installare la PR, eseguire preparazione sul server senza richieste attive,
collaudare somma.py + unittest con 8B, verificare thinking, RAM/swap, tempi e stop.
PRG-01/PERF-01 restano aperti; nessuna capacità reale del nuovo modello attestata.
