# Activity Explorer

La pagina `#activity` mette in primo piano un explorer ispirato alla disposizione
di Protocol Explorer: storico e passaggi a sinistra, rete/sequenza al centro,
ispettore a destra e flusso cronologico degli eventi in basso.

## Fonti e significato

- Riutilizza le API autenticate esistenti per runtime, run recenti, operazioni,
  eventi transazionali e diagnostica. Non aggiunge endpoint o esecutori.
- Le frecce derivano esclusivamente da `span_id` e `parent_span_id` registrati.
  Operazioni e osservazioni del provider senza correlazione non generano frecce.
- Distingue strumenti esposti al modello, chiamate tracciate e operazioni
  persistenti. Il numero dei passaggi riguarda il campione caricato.
- L'ispettore mostra fonte, stato, durata, errori, parametri/risultati delle
  operazioni e confronto modello richiesto/riportato con macchina registrata.
- Il replay è una lettura locale degli eventi: non invoca strumenti e non ripete
  azioni. Lo stato globale del run resta quello attuale. Gli eventi futuri non
  anticipano la conclusione di un passaggio nel replay.

## Successo e verifica

Un run `completed` non certifica che la risposta soddisfi la richiesta.
L'explorer segnala modelli divergenti, operazioni fallite/incerte, genitori
assenti e tracce senza evento finale. Non deduce l'intenzione dal testo.
Il confronto manuale richiesta/risultato contiene annotazioni temporanee della
vista: non salva certificazioni sul server. Le approvazioni e la registrazione
della verifica degli effetti restano nei controlli operativi esistenti.

## Limiti

- Diagnostica best-effort, soggetta a perdita e scadenza: mancanza di una traccia
  non significa mancata esecuzione. I contatori di perdita sono del processo.
- Ultimi 30 run persistenti più run attivi; massimo 100 operazioni per selezione,
  con avviso al raggiungimento del limite; rete limitata a 40 nodi, sequenza
  consultabile per tutti i passaggi caricati.
- Live ogni 5 secondi, sospeso nella scheda nascosta. La diagnostica live mostra
  gli ultimi 100 eventi; caricare pagine precedenti mette il live in pausa.
  Gli eventi persistenti avanzano dal cursore già caricato. Le risposte in
  ritardo non sostituiscono il campione messo in pausa.
- Niente nuovi prompt, ragionamenti o output dei tool nell'archivio diagnostico.
- Layout adattivo e supporto a tastiera/riduzione movimento. Collaudo visivo su
  browser e verifica sul Debian reale ancora da completare.

## Validazione locale

185 test frontend superati, build TypeScript/Vite riuscita e `git diff --check`
superato. Test mirati su replay storico, evidenze mancanti, divergenze modello,
effetti incerti, origine dei fatti persistenti, topologie cicliche, polling e
preservazione dei controlli operativi. Nessun deploy o inferenza reale eseguiti.
