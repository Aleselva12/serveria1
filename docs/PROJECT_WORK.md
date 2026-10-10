# Piano di consolidamento del server

Aggiornamento: 10 ottobre 2026. Baseline esaminata: main, commit 882ed5f.
Questo è il primo inventario operativo derivato dall'audit e dai promemoria sparsi.
La revisione continua durante gli interventi: non è una certificazione di ogni
percorso né del server installato.

La lista visualizzata dalla Home è in
[project-work.json](../frontend/src/services/project-work.json).
Ogni voce ha ID stabile, categoria, priorità, tipo, stato, criterio di completamento
e sorgenti da riesaminare. Questa tabella è una fotografia del primo lotto;
per lo stato corrente fare riferimento alla lista della Home.

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

## Attività aperte (aggiornate dopo i lotti implementati)

### Utilità quotidiana

| ID | Lavoro | Priorità | Tipo | Stato |
|---|---|---|---|---|
| REM-01 | Telefono tramite Tailscale | P1 | Collaudo | Da collaudare |
| BKP-01 | Ripristino completo su ambiente sacrificabile | P1 | Collaudo | Da collaudare |
| AUTH-01 | Login dei dispositivi dietro il proxy | P2 | Correzione | Da fare |
| SHR-01 | Aprire un link condiviso dopo il login | P2 | Funzione | Da fare |
| SEC-01 | Dipendenze e confini di accesso | P2 | Correzione | Da fare |
| FILE-03 | Upload e foto da telefono | P2 | Collaudo | Da collaudare |
| EXT-01 | Programmi remoti non IA | P3 | Decisione | Successivamente |

### Funzioni

| ID | Lavoro | Priorità | Tipo | Stato |
|---|---|---|---|---|
| OBS-01 | Errori Ollama utili e riservati | P1 | Correzione | Da fare |
| DOC-01 | Descrizioni coerenti con ciò che esiste | P2 | Correzione | Da fare |
| PRG-01 | Verifiche del Programmatore nel server | P2 | Funzione | Da fare |
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
| MEM-01 | Contesto e memoria dopo le ottimizzazioni | P2 | Decisione | Decisione da prendere |
| PERF-01 | Misurare la latenza prima di ottimizzare | P2 | Collaudo | Da collaudare |
| OLL-01 | Un solo endpoint e trasporto Ollama | P2 | Correzione | Da fare |
| TEST-01 | Suite affidabile su PC e Linux | P2 | Correzione | Da fare |

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
