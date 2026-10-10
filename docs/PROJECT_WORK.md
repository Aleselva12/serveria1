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

## Inventario iniziale

### Utilità quotidiana

| ID | Lavoro | Priorità | Tipo | Stato iniziale |
|---|---|---|---|---|
| DEP-01 | Avvio server e persistenza del selettore | P1 | Correzione | Preparato in locale |
| DEP-02 | Manutenzione con gli stessi override | P1 | Correzione | Preparato in locale |
| REM-01 | Telefono tramite Tailscale | P1 | Collaudo | Da collaudare |
| BKP-01 | Ripristino completo su ambiente sacrificabile | P1 | Collaudo | Da collaudare |
| AUTH-01 | Login dei dispositivi dietro il proxy | P2 | Correzione | Da fare |
| SHR-01 | Aprire un link condiviso dopo il login | P2 | Funzione | Da fare |
| SEC-01 | Dipendenze e confini di accesso | P2 | Correzione | Da fare |
| FILE-03 | Upload e foto da telefono | P2 | Collaudo | Da collaudare |
| EXT-01 | Programmi remoti non IA | P3 | Decisione | Successivamente |

### Funzioni

| ID | Lavoro | Priorità | Tipo | Stato iniziale |
|---|---|---|---|---|
| MOD-01 | Cambio modello per tutti gli agenti | P1 | Correzione | Da fare |
| OBS-01 | Errori Ollama utili e riservati | P1 | Correzione | Da fare |
| DOC-01 | Descrizioni coerenti con ciò che esiste | P2 | Correzione | Da fare |
| PRG-01 | Verifiche del Programmatore nel server | P2 | Funzione | Da fare |
| PRG-02 | Ciclo release e recupero | P2 | Collaudo | Da collaudare |
| FILE-01 | Cora esplora, legge e cerca nei file autorizzati | P2 | Funzione | Da fare |
| FILE-02 | Cora gestisce file e copie IA | P2 | Funzione | Da fare |
| SYNC-01 | Originali e copie IA | P3 | Decisione | Decisione da prendere |
| AUTO-01 | Esecutore delle automazioni grafiche | P3 | Funzione | Da fare |
| OCR-01 | Leggere PDF scansionati | P3 | Funzione | Da fare |
| AUD-01 | Audio locale e diarizzazione opzionale | P3 | Collaudo | Da collaudare |
| MAIL-01 | Gmail e preventivi | P3 | Collaudo | Da collaudare |
| FUT-01 | Obiettivi avanzati | P3 | Decisione | Rinviato |

### Efficienza

| ID | Lavoro | Priorità | Tipo | Stato iniziale |
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
