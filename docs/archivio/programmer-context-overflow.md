# Programmatore: contesto durante le chiamate tool

## Riscontro locale del 18 ottobre 2026

Il vecchio run `92805733` registrava solo `ValueError` dopo tre letture riuscite.
Il nuovo run `59e76e8f` fornisce una causa diversa e precisa: `ContextOverflow`.
Con qwen3:8b e finestra di 16384 token, il budget applicativo degli input era
11048 token stimati, dopo riserva per schema tool e generazione. Le stime dei
messaggi crescono da 1996 a 4400, 6595, 8868 e 10942; la chiamata seguente viene
bloccata prima di raggiungere Ollama. L'ultimo prompt realmente elaborato era di
6561 token: non è una prova di RAM/VRAM esaurita né di finestra fisica piena.

Il run contiene tre tentativi `programmer_write_file` respinti dalla validazione.
Una riproduzione con il modello locale in un workspace separato ha mostrato
`workspace_id` mancante e `content` di tipo oggetto anziché stringa. Il messaggio
di validazione precedente poteva includere l'intero input, duplicando codice
generato. L'adapter LangChain/Ollama installato ha inoltre una euristica che
decodifica nuovamente le stringhe JSON nei singoli argomenti: un `content` valido
contenente un file JSON diventa un oggetto, provocando lo stesso `string_type`
anche quando il modello ha rispettato il contratto. La correzione preserva i tipi
dell'envelope originale senza reinterpretare il contenuto dei file, sia nel
trasporto sincrono che asincrono. Gli oggetti realmente inviati al posto di
stringhe restano errori; non si ricostruisce il testo dopo una conversione lossy.
Ogni AIMessage conservava inoltre `reasoning_content`, che l'adapter
Ollama reinvia come `thinking` nelle chiamate successive.

Un altro run recente, `ce7a01a8`, fallisce invece con HTTP 404 del provider:
modello/risorsa non trovato. Non si tratta di overflow e non viene ritentato
come tale. La selezione del modello del proprietario non viene cambiata.

## Correzione

- Il solo ingresso del modello esclude il ragionamento e i metadati delle
  risposte precedenti; i messaggi originali del grafo e le prove restano integri.
  Il nuovo ragionamento continua a essere mostrato durante ogni chiamata.
- I tool vengono validati prima dell'esecuzione. Errori compatti riportano nomi
  dei campi, tipi attesi e `executed=false`, senza riecheggiare codice o valori
  privati. Non vengono inventati workspace, contenuti o hash mancanti.
- L'adapter preserva esattamente le stringhe JSON contenute negli argomenti;
  oggetti e liste strutturati mantengono il loro tipo originale.
- Alla correzione degli argomenti qwen3 usa una chiamata senza thinking, per
  concentrarsi sullo schema. Le normali fasi di programmazione mantengono la
  politica del modello. Il budget viene ricontrollato anche durante i recuperi.
- Se il turno non entra ancora, soltanto gli scambi tool già completati sono
  proiettati in un registro deterministico: nomi, identificativi, percorsi,
  hash, esiti, approvazioni pendenti e verifiche fallite rimangono disponibili.
  I contenuti lunghi recuperabili vengono omessi esplicitamente con impronta;
  il modello deve rileggere i file quando necessari. Il registro non esegue
  operazioni e non sostituisce le evidenze originali.
- Istruzioni di sistema, richiesta corrente e scambi incompleti non vengono
  troncati per forzare il budget. Cancellazioni, errori di trasporto ed effetti
  incerti continuano a interrompere l'esecuzione senza replay.
- Gli eventi diagnostici conservano ora conteggi del contesto, compattazione,
  validazione e causa di arresto; non conservano prompt o ragionamento privato.

## Regressioni

I test coprono rimozione del thinking senza mutare lo stato, compattazione di
scambi completi, conservazione di approvazioni e verifiche fallite, rifiuto di
istruzioni troppo grandi e protocolli incompleti, errori di schema senza input
privati, e un grafo completo con sei file realmente salvati nel workspace di test
e una scrittura malformata corretta al passaggio successivo. I test sono inclusi
nel profilo Windows usato da CI e aggiornamento desktop.
