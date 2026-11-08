# Roadmap ad albero Cora

## Fonte strutturale

La fonte autorevole della **struttura** è `Aleselva12/qwe`, branch
`progetti/cora-serveria`. `cora-plan.snapshot.json` è la copia distribuita del
`cora-plan.json` selezionato. Per cambiare stelle, radici, tronco, rami, pianeti,
lune o relazioni strutturali si aggiorna la fonte e poi si rigenera/copia la
snapshot: i test e il classificatore non devono creare automaticamente nuovi nodi.

La roadmap precedente resta nei dati storici. La pagina non modifica il
`localStorage` di Atlas e non inventa commit, versioni o risultati mancanti.

## Visualizzazione

La vista principale è una costellazione 2D con un unico albero connesso:

- **radici** in basso per dipendenze, hardware, modelli, librerie e basi operative;
- **tronco** centrale per orchestrazione e scheletro di sistema;
- **rami** in alto per funzionalità e programmi;
- stelle principali con pianeti/lune mostrati su selezione.

Zoom, trascinamento, pieno schermo e ritorno all'albero completo servono
all'esplorazione. Le schede espongono Passato/Presente/Futuro con i dati realmente
disponibili. La vecchia rappresentazione a elenco non è una seconda roadmap.

## Stato ed evidenze runtime

La struttura resta manuale, mentre Cora proietta automaticamente sopra i nodi:

- stato obiettivi da `project-status.generated.json`;
- esiti dal registro salute backend;
- mapping test→nodi senza modificare la gerarchia;
- evidenze storiche Atlas conservate separatamente in `atlas-evidence.json`.

`orchestrator_v1_contract` può fornire evidenza strutturale alle stelle del tronco
associate. Un test può cambiare stato/colore o segnalare un problema, non aggiungere,
spostare o fondere stelle.

## Classificatore locale

`RoadmapPriorities.tsx` usa il classificatore locale soltanto su **clic esplicito**.
La richiesta è limitata a un insieme bounded di task/nodi (attualmente massimo 8) e
passa problemi, obiettivi e contesto aggiuntivo al modello locale configurato da
`CORA_ROADMAP_CLASSIFIER_MODEL`.

Il classificatore serve a suggerire priorità/urgenza e a riassumere il contesto.
Non usa servizi cloud, non scrive file della roadmap, non chiama `updateRoadmap` e
non modifica automaticamente la mappa. Il proprietario decide ogni modifica
strutturale.

## Aggiornamento e collaudo

La sequenza W1/W2/W3 non viene più letta dal campo `nextWork` della snapshot.
Quando cambia la fonte qwe, aggiornare la snapshot e verificare ID, relazioni,
mapping delle evidenze e rendering. Per il collaudo sul Debian usare il commit
**effettivamente installato** dall'updater e verificare i servizi reali: una CI verde
o una snapshot nuova non certificano da sole il server in esecuzione.


## Colori e descrizioni della verifica

La pagina mostra, in ordine: sequenza operativa, albero, analisi dei prossimi passi,
collaudi e comando di aggiornamento. “Aggiorna albero” rilegge registro e versione,
senza avviare test o inferenza; il pannello collaudi aggiorna gli stessi dati ad ogni
avanzamento. Le descrizioni della verifica usano la stessa funzione dei colori.
La nota statica è separata sotto “Descrizione di progetto”.

- **Grigio** — elemento futuro oppure collaudo assente, scaduto o senza attribuzione alla versione attiva.
- **Verde** — verifica valida sul Debian per la versione attiva, oppure osservazione manuale datata e limitata al nodo e al percorso provati.
- **Giallo** — ambito parziale, rifinitura aperta o sviluppo previsto. Il registro dell’8 novembre include il messaggio HTTP 502 a worker disattivato e le regole di autoselezione del modello e di gestione del worker offline.
- **Arancione** — criticità documentata o fallimento parziale.
- **Rosso** — fallimento effettivo dei controlli end-to-end associati sul Debian per la versione attiva.

Un fallimento attuale prevale sull’osservazione manuale. Un verde manuale
vale per il perimetro descritto nella scheda e non certifica il commit installato
o l’intero ramo. Il [registro manuale dell’8 novembre](../../../docs/NODE_VERIFICATION.md#registro-manuale-del-proprietario--8-novembre-2026)
riporta i nodi verificati e i limiti delle prove.

## Prima estensione dei controlli

Quattro suite isolate riutilizzano unittest e il runner una tantum: esplorazione file, ciclo di vita file, accesso/confinamento e documenti Word. Undici ulteriori pianeti/lune ricevono associazioni esplicite, includendo le prove già disponibili per bozze MIME e PDF preventivi. Sono controlli sintetici: non certificano account Gmail, NAS, installazione Debian o browser reali. Il risultato compare nel registro condiviso e nella scheda del nodo, senza trasformare una simulazione in verde E2E.

## Estensione suite per nodi

`core/tree_verification_suites.py` dichiara 29 ulteriori suite, i test riutilizzati, i nodi associati e i limiti della prova. Catalogo e runner leggono questa fonte; un test verifica che ogni ID sia presente nella snapshot e nel mapping frontend, senza duplicati né associazioni a elementi pianificati. La scheda mostra la descrizione di ambito accanto agli esiti. La copertura diretta totale è 143/455 pianeti e lune; resta copertura di regressione isolata, non prova automatica di funzionamento reale.


Gli ambiti esplicitamente futuri (espansione GPU, espansione locale, NAS, ricerca modelli, trust futuro, bus distribuito, Custode, OCR e schede cliente) e i loro sottoelementi sono `planned`: 26 elementi riclassificati da parziali a non presenti. La struttura e gli identificativi restano invariati; gli altri parziali non vengono riclassificati senza evidenza.

## Indicatori indipendenti — tranche autonoma Atlas

Accanto al colore storico della mappa, ogni stella, pianeta e luna mostra due
indicatori: **S** (sviluppo dichiarato) e **C** (collaudi del solo nodo).
La legenda è disponibile nella scheda. Gli indicatori compaiono anche nei dettagli
dei pianeti e delle lune; selezionando un sottoelemento, il suo titolo accompagna
sempre i suoi indicatori, senza attribuirli alla stella.

- Sviluppo: grigio per `planned`/`idea` o stato sconosciuto, blu per `partial`,
  verde per `present`. Un test superato non cambia lo sviluppo dichiarato.
- Collaudi: grigio senza evidenza valida; giallo per prove reali parziali o
  rifiniture manuali; arancione per criticità documentate o fallimenti parziali;
  rosso per fallimento di tutti gli E2E associati; verde per esito reale completo
  oppure osservazione manuale datata, esplicitamente circoscritta.
- Un esito scaduto, privo di attribuzione, di un altro commit o solo CI non è un
  fallimento corrente del Debian. Un successo sintetico non certifica la funzione.
- Nessuna propagazione tra i nuovi indicatori: un fallimento della luna non
  cambia quelli del pianeta. `starTone`, filtri e colore centrale conservano
  il comportamento storico; la diagnosi delle priorità resta missione assistita.

La funzione `verificationIndicator` usa il registro esistente, senza eseguire
nuovi test o inferenze. I test in `tree_indicators.test.mjs` coprono sviluppo,
provenienza, scadenza, fallimenti, conferme manuali e indipendenza del genitore.
La suite frontend controlla anche mapping, riferimenti e filtri esistenti.
