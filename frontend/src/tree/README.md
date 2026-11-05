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
