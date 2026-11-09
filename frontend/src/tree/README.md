# Roadmap ad albero Cora

## Fonte strutturale

La fonte autorevole della **struttura** è ora **questa repository ServerIA**, nel file
`frontend/src/tree/cora-plan.snapshot.json`. `Aleselva12/qwe` è un archivio legacy:
non è più necessario aggiornare qwe né sincronizzare modifiche strutturali da lì.
Stelle, radici, tronco, rami, pianeti, lune e relazioni vengono revisionati qui,
con ID stabili e controllo delle dipendenze. Test e classificatore non creano
automaticamente nodi o relazioni.

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
`CORA_ROADMAP_CLASSIFIER_MODEL` (default `qwen3:1.7b`). L'API concede fino a 420 secondi all'inferenza. Le valutazioni completate sono conservate in PostgreSQL e alimentano le priorità visibili in Home.

Il classificatore serve a suggerire priorità/urgenza e a riassumere il contesto.
Non usa servizi cloud, non scrive file della roadmap, non chiama `updateRoadmap` e
non modifica automaticamente la mappa. Il proprietario decide ogni modifica
strutturale.

## Aggiornamento e collaudo

La sequenza W1/W2/W3 non viene più letta dal campo `nextWork` della snapshot.
Quando cambia la struttura in ServerIA, verificare ID, relazioni,
mapping delle evidenze e rendering. Per il collaudo sul Debian usare il commit
**effettivamente installato** dall'updater e verificare i servizi reali: una CI verde
o una snapshot nuova non certificano da sole il server in esecuzione.


## Colori e descrizioni della verifica

La pagina mostra, in ordine: sequenza operativa, albero, analisi dei prossimi passi,
collaudi e comando di aggiornamento. “Aggiorna albero” rilegge registro e versione,
senza avviare test o inferenza; il pannello collaudi aggiorna gli stessi dati ad ogni
avanzamento. Le descrizioni della verifica usano la stessa funzione dei colori.
La nota statica è separata sotto “Descrizione di progetto”.

- Grigio: stato `planned`/`idea`, quindi elemento non presente.
- Giallo: elemento `partial`, senza problemi rilevati né un collaudo E2E associato
  ancora da provare. Non certifica il funzionamento completo.
- Rosso “non provato”: elemento presente privo di prove valide, oppure collaudo
  E2E associato ma mancante/scaduto/non attribuibile alla versione attiva.
  È distinto dal rosso “collaudo fallito”, che richiede un fallimento reale.
- Verde: E2E Debian valido sulla versione attiva e controlli associati superati.
  Figli grigi non presenti e gialli parziali non impediscono questo risultato;
  nemmeno una voce nella lista degli sviluppi futuri lo invalida.
- Arancione: problemi documentati, fallimenti parziali o sottoelementi presenti
  non provati. Le criticità non vengono ignorate perché un nodo è parziale.

Rami e aree delle radici aggregano i figli: verde se tutti i figli attivi sono
verdi/gialli, arancione per criticità miste, rosso se tutti quelli attivi sono
falliti/non provati. Un insieme di soli obiettivi non presenti rimane grigio.
Il verde di un contenitore è un riepilogo, non un nuovo collaudo E2E.

La revisione dell'API che ha eseguito il controllo deve corrispondere alla release attiva per attribuire l'esito a quella versione. Gli esiti sintetici e le evidenze storiche restano distinguibili dai collaudi E2E.

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

## Localizzazione dei problemi e relazioni tipizzate (2026-11-09)

Le criticità note sono attribuite al **pianeta o alla luna responsabile** quando
il catalogo permette di identificare un ambito specifico. Un problema generale
non attribuibile con sufficiente precisione rimane sulla stella: non viene
assegnato arbitrariamente a un sottoelemento. La scheda della stella raccoglie
anche i problemi dei discendenti e mostra l'ID proprietario; filtri e copia
riepilogo includono gli stessi problemi localizzati. Un problema documentato
non è automaticamente un test fallito né una prova che il servizio sia guasto.

Le relazioni `depends_on`, `uses`, `communicates_with`, `produces_for` sono
integrate da `verified_by` (collegamento con l'ambito della verifica) e
`shares_evidence_with` (lo stesso risultato di test è utilizzato per più nodi).
Questi collegamenti sono **descrizioni architetturali proposte**, non nuovi
risultati di test, e non cambiano la gerarchia radici/tronco/rami. In particolare
un controllo condiviso non equivale a due collaudi indipendenti. La loro
rappresentazione nel pannello relazioni serve a rendere visibile la distinzione.

Per la prossima fase rimangono separati: censimento dei link al codice, revisione
delle classificazioni di implementazione, ridefinizione delle responsabilità
tra Planner/Runtime/Worker e revisione del classificatore delle priorità.

## Atlas V3 — fase 1: contratti, senza cambiare la facciata

Il catalogo ServerIA mantiene invariati tutti i nodi, i loro ID e la gerarchia.
Il campo `v3` nella snapshot introduce il registro canonico `issues`, la
struttura `evidence` e il dizionario `nodeResponsibilities`. Le relazioni
tipizzate rimangono nel campo top-level `relations`, senza duplicazioni.

- **Stella:** responsabilità riconoscibile; **pianeta:** capacità; **luna:**
  funzione specifica verificabile. La revisione delle singole assegnazioni
  avverrà nella fase 2, non viene inferita automaticamente da Graphify.
- **Issue:** un solo `ownerNodeId`, possibili `affectedNodeIds`, tipo, stato,
  gravità ed evidenze collegate. I 19 problemi esistenti sono migrati come
  `legacy`, `unclassified`, `open`, senza inventare gravità o verifiche.
- **Evidenza:** provenienza esplicita (codice, CI, Debian, osservazione manuale),
  ambito e commit quando noti; un collegamento non certifica il runtime.
- **Relazione:** dipendenza o uso tra nodi, distinta dalla parentela dell'albero.
- **Compatibilità:** `knownIssues` resta temporaneamente una proiezione V2
  per la pagina attuale. Non sommare `knownIssues` e `v3.issues`: sono gli
  stessi problemi. Durante la fase 2 si dovrà scegliere un unico punto di
  scrittura e migrare la lettura UI prima di eliminare la proiezione.

La fase 1 non modifica il rendering, i colori, il planner né i criteri dei
test esistenti. La fase 2 affronterà responsabilità, duplicazioni e confini
architetturali; solo dopo verrà aggiornata la facciata.

### Triage iniziale delle 19 criticità

Le 19 note legacy sono state classificate per **natura del lavoro** e non per
stato di salute. Nessuna nota viene convertita automaticamente in bug verificato.
La gravità resta `unknown`, lo stato `open` indica che il punto richiede ancora
una decisione o una prova, non che il componente sia guasto. Il registro V3
conserva testo e proprietario originari; la UI V2 continua a leggere la
proiezione `knownIssues`. I test controllano che le due rappresentazioni non
divergano durante la transizione.

## Atlas V3 — fase 2: revisione responsabilità, prima passata

Tutte le 45 stelle hanno ora una classificazione **proposta** in
`v3.nodeResponsibilities` (capacità utente, servizio interno,
infrastruttura, governance). La classificazione riguarda la responsabilità,
non l'esito dei test. Le decisioni motivate su sette confini trasversali sono
registrate in `v3.responsibilityReview`, con file di codice dove verificati.

Non sono stati spostati pianeti, lune o stelle: prima di modificare la
gerarchia occorre confrontare i confini funzionali a livello di sotto-nodo.
I confini T2/R6.2, T9/T4/F1, B1/B2/B3/D2 e T10/T11/D5 sono mantenuti
separati, con relazioni trasversali per le dipendenze. Il problema
dell'updater comune alle app richiede ancora un owner unico.

Questa revisione non certifica integrazione o funzionamento reale.

## Vista sintetica V3 — proposta, non nuova gerarchia

`v3.atAGlanceReview` propone tre livelli: panorama (radici/tronco/rami),
responsabilità (stelle raggruppate), operatività (pianeti/lune e prove).
I gruppi sintetici coprono tutte le 45 stelle una sola volta e **non**
modificano `parent`, ID, status o codice della UI. Le relazioni trasversali
sono visualizzabili su richiesta, non linee permanenti nell'albero.
Un problema su una luna è mostrato come conteggio di attenzione nella stella
senza dichiarare guasto l'intero programma. Le verifiche runtime restano
separate dall'implementazione. Sei confini ambigui sono elencati come review
flags prima di un eventuale reparenting.

## Fase 2 — primo cambiamento strutturale canonico

La stella `T14` (Approvazioni ed effetti autorizzati) è stata **aggiunta
come obiettivo pianificato** nel tronco, con due pianeti e quattro lune
tutti `planned`. Non è una dichiarazione di approvazioni operative:
nessuna verifica runtime è attribuita a T14. La sua responsabilità è
distinta da `R6.2` (policy e permessi), `T2` (contratti capability) e
`T4` (stato dei run). Le dipendenze verso questi tre nodi sono proposte.

Il catalogo passa da 515 a 522 nodi: 46 stelle, 153 pianeti, 308 lune.
Le 515 identità storiche, i 19 problemi e i loro proprietari rimangono
invariati. T15 e T16 restano proposte esterne alla gerarchia, non
funzioni implementate. La posizione di T14 nella costellazione è
riservata senza rifacimento della pagina.

La vista sintetica e la revisione dei confini sono ancora proposte:
nessun test automatico o collaudo sul Debian è implicito nel cambio
di schema.
