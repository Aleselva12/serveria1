# Programmatore: stabilizzazione e Context Manager minimale

> Aggiornamento: il percorso semantico e la configurazione attuale sono descritti
> in [programmer-semantic-router.md](programmer-semantic-router.md). Il resto di
> questo documento descrive la prima implementazione e le sue misure storiche.

Base analizzata: `5d58af9` (main). Nessun merge o rilascio automatico.

## Diagnosi e modifiche

- Il grafo aveva già `fit_messages()` e 21 tool governati. Tutti gli schemi erano
  inviati ad ogni iterazione; Graphify è una consultazione su richiesta, non un
  caricamento obbligatorio del grafo nel prompt.
- Le chiamate multiple del modello venivano troncate alla prima, senza risultati
  per le altre. Ora il messaggio originale è conservato: si esegue una sola
  operazione e le altre ricevono un risultato esplicito «non eseguito». Il modello
  deve rivalutarle, evitando esecuzioni parallele o scritture su hash obsoleti.
- Il grafo poteva terminare su una risposta vuota/malformata. Ora fallisce in modo
  esplicito, senza retry automatici. Timeout/errori di Ollama continuano a propagarsi.
- Si ricontrolla cancellazione/scadenza dopo la risposta del modello e dopo i tool.
  Il gestore errori di ToolNode propaga RunCancelled/RunTimedOut; le eccezioni
  BaseException di arresto, effetto incerto e durabilità continuano a propagarsi.
- La fine del grafo non interrogava le evidenze di verifica: ora registra gli ultimi
  check per profilo che corrispondono al digest attuale del workspace, aggiungendo
  un resoconto fattuale alle risposte testuali. Una verifica interrotta/fallita
  successiva sostituisce il successo precedente. Nessun controllo viene eseguito
  automaticamente e un run completato non equivale a codice verificato/attivato.
- Le protezioni esistenti per hash, snapshot, check Docker, permessi, approvazioni,
  commit e rilascio non sono state cambiate. La selezione non è un'autorizzazione.

## Attivazione progressiva

`CORA_CONTEXT_MANAGER_ENABLED=false` è il default nel codice e in `.env.example`.
Per una prova locale impostare `true` nell'ambiente dell'API (nel deployment attuale,
`deploy.env`) e ricreare l'API tramite la procedura abituale. Solo il programmatore
legge questo flag. Con `false`, prompt e schemi inviati seguono il percorso precedente;
le correzioni di stabilità e la registrazione delle evidenze restano attive.

Il componente `programmer_agent/context_manager.py`:

1. Seleziona deterministicamente gli schemi dalla richiesta umana corrente.
2. Conserva sempre elenco/lettura/ricerca file, catalogo, skill, diff, check e componenti.
3. Aggiunge gruppi per modifica, automazioni, grafo e rilascio; nomi tool espliciti
   restano selezionabili. Richieste non riconosciute mantengono tutti i 21 tool.
4. Riusa `fit_messages()` senza modificare il budget condiviso: istruzioni, richiesta
   corrente e scambi tool completi restano obbligatori; i turni precedenti vengono
   selezionati dal meccanismo esistente.
5. Recupera dati tramite gli strumenti già governati (`search_code`, `read_file`
   paginato, skill, grafo). Dopo una chiamata a `programmer_catalog` o un risultato
   tool in errore espone tutti i tool per il resto del turno. Questo permette
   recuperi aggiuntivi anche quando il classificatore iniziale non coglie il task.

Non sono introdotti LLM aggiuntivi, Jev, API cloud, riassunti automatici, database,
nuovi tool, modifiche ai file dell'utente o nuove procedure di rilascio.

## Metriche

Per entrambi i percorsi, `run.timings.programmer_context` (ultimi 100 campioni) e
l'event bus esistente registrano:

- `context_call`: flag, motivo selezione, nomi tool, stime separate messaggi/schemi,
  durata locale della preparazione + chiamata modello, tipo errore;
- `prompt_eval_count`, `eval_count`, `total_duration` quando forniti da Ollama;
  assenza significa dato non disponibile, non zero;
- `tools`: tool eseguito, tool rinviati, numero di risultati in errore;
- `verification`: digest e ultimi esiti dei profili sul workspace corrente.

Le stime sono l'euristica conservativa di `core/context_budget.py`, non token
misurati da un tokenizer. I callback preesistenti mantengono tempi e dettagli
Ollama; il nuovo campione li collega alla selezione degli strumenti. I payload
non contengono prompt, sorgenti, argomenti dei tool o messaggi di errore sensibili.

## Verifiche riproducibili

Installare le dipendenze test già dichiarate dal progetto, quindi:

```sh
python -m unittest discover -s tests -p 'test_programmer*.py'
python tests/programmer_context_benchmark.py
```

Il benchmark usa un modello **simulato**, ma esegue davvero LangGraph, lettura,
scrittura nella copia temporanea e verifica della sintassi. Solo modello, contesto
permanente e persistenza/policy DB sono simulati. Il sorgente resta invariato.
Due scenari (modifica valida e sintassi errata) vengono eseguiti con flag false/true.
Il risultato campione è in `docs/programmer-context-ab.json`.

Nel task di modifica, i tool passano da 21 a 12 e la stima degli schemi da 4056 a
2299 token (-43,3%). Il messaggio iniziale passa da 1515 a 1694 token per le istruzioni
aggiuntive; messaggi + schemi passano da 5571 a 3993 (-28,3%). Gli esiti verificati
coincidono tra i due percorsi, sia nel caso positivo sia in quello negativo.
I tempi del benchmark sono overhead locale con un modello simulato e includono
effetti di inizializzazione: **non dimostrano un miglioramento di latenza Ollama**.

La suite base del programmatore su `5d58af9`: 23 test, 22 superati e 1 saltato.
I test aggiunti coprono selezione/fallback, recupero catalogo, dati non autorevoli,
protocollo tool, cancellazione, errori modello, overflow ed evidenze obsolete.
Suite mirata finale: **100 test, 89 superati, 11 saltati**, nessun errore.
Comprende programmatore, context manager, contratti capability, updater, cambio
modello, fondamenti runtime, policy generazione, errori provider e budget memoria.
I salti sono 10 test PostgreSQL e 1 test del CLI Graphify non installato.

Il test del cambio modello è aggiornato per far restituire AIMessage validi ai mock,
mantenendo le stesse asserzioni sulla risoluzione del modello.

## Aperto e limiti

- Da eseguire sul server: A/B sullo stesso modello, workspace iniziale e task,
  prima false poi true, con almeno tre ripetizioni dopo il riscaldamento. Confrontare
  token reali, durata modello, chiamate/errori e check sul digest finale. Usare copie
  separate per i task di scrittura; includere lettura, correzione con test, richiesta
  ambigua, tool mancante e overflow. Non pubblicare/applicare rilasci nel benchmark.
- Non è stato misurato Ollama/GPU reale né il deployment completo. I test che
  richiedono PostgreSQL/Docker reale possono essere saltati dal loro gate esistente.
- Il selettore lessicale IT/EN è conservativo ma non comprende semanticamente ogni
  richiesta. Il fallback/catalogo mantiene raggiungibili i tool esclusi.
- Il turno corrente molto grande continua a generare ContextOverflow: non viene
  troncato, riassunto o archiviato automaticamente. Letture paginabili riducono il
  rischio, ma compattazione con recupero di risultati precedenti è un passo futuro.
- Il resoconto finale documenta i check, non certifica la correttezza del testo LLM
  né impedisce ogni affermazione inesatta. La verifica della sintassi non certifica
  comportamento, build o integrazione; restano validi i gate dei componenti/rilasci.
