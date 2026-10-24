# Chat adattiva e integrazione del design Frontend — 25 ottobre 2026

## Interfaccia

Riferimento letto dal progetto Frontend: Serveria Design Studio (`287eaebb-ada8-4b6d-aee3-3a4ef1eaf18e`), pagina chat in `src/serveria/Serveria.tsx` e relativo design system in `src/styles.css`. Adattata al frontend React reale senza importare mock, database Lovable o contenuti dimostrativi.

- Superfici chiare, accento salvia, sidebar conversazioni, intestazione Cora e compositore sempre visibile; solo la conversazione scorre.
- Suggerimenti iniziali preparano una bozza: non inviano messaggi né eseguono strumenti.
- Spazi collegati aprono le pagine reali File/Libreria, Calendario, Audio, Programmatore e Home/programmi. Nessuna nuova integrazione esterna fittizia.
- Markdown/GFM per risposte, tabelle e codice; HTML escluso, link pericolosi filtrati dal renderer. Test specifici inclusi.
- Fonti consultate raccolte; attività e thinking separati dalla risposta nel pannello laterale.
- Profilo del modello e della macchina effettivamente selezionati, capacità dichiarate, contesto configurato e distinzione fra risposta progressiva locale e risposta ricevuta al termine dal worker.
- Errori noti spiegati nella chat, ID esecuzione e collegamento ad Attività; nessun replay automatico.

## Difetti riprodotti e correzioni

Una lettura Libreria può restituire fino a 120.000 caratteri. Il precedente fit_messages rifiutava l'intero turno dopo una lettura riuscita quando il risultato superava il budget. Una regressione riproduce il problema con il cliente cercato vicino alla fine del documento sintetico.

La proiezione per il modello ora seleziona estratti pertinenti dei soli risultati di lettura Libreria, conservando identità della fonte, chiamate e risposte tool, richiesta utente e messaggi originali. Gli estratti sono marcati esplicitamente come parziali: non attestano di contenere tutte le annotazioni o la data più recente. Non vengono accorciati arbitrariamente risultati di scrittura o strumenti sconosciuti; resta il rifiuto quando istruzioni/richiesta non entrano nel budget. Il grafo di regressione legge una volta e completa la risposta senza rieseguire il tool.

Il thinking precedente resta nei dati originali ma non viene reinviato ad ogni passaggio del modello. La lettura del campo thinking è indipendente dall'attivazione della generazione thinking: il parser conserva la separazione senza forzare think=true.

Questa è una causa riprodotta compatibile con le schermate dell'utente, non una diagnosi certificata delle esecuzioni Debian mostrate: i loro log conclusivi non sono stati acquisiti.

## Capacità dei modelli

`core/model_profiles.py` legge `/api/show` per il provider locale e `/model-info` per il worker selezionato, con cache breve separata per macchina/modello. Nessuna selezione automatica di modello o macchina. I metadati indicano capacità dichiarate, non qualità o collaudo operativo.

- Contesto limitato dalla configurazione Cora e dal massimo dichiarato dal modello, usato sia nell'inferenza sia nel budget di chat e specialisti, incluso il Programmatore.
- Nessun thinking imposto in base al nome Qwen. Supportati i valori booleani e i livelli dichiarati; in assenza di metadati viene lasciato il default del provider.
- Un modello che dichiara di non supportare strumenti può conversare senza strumenti; una richiesta con strumenti fallisce esplicitamente anziché cambiare provider.
- Worker vecchio o metadati indisponibili: capacità indicate come non verificate, senza fallback verso Ollama locale. Per rendere disponibili le capacità del desktop occorre aggiornare il worker; la chat esistente resta compatibile.
- `/model-info` richiede l'autenticazione esistente, modello installato e restituisce solo metadati selezionati; non espone prompt o template, non scarica modelli e non avvia inferenza.

## Verifiche

- Suite Linux con PostgreSQL 16/pgvector temporaneo: 522 test, OK; una esclusione per Graphify CLI opzionale.
- Frontend: 125 test, OK; build TypeScript/Vite e smoke check OK. Resta l'avviso sul bundle oltre 500 kB.
- Ulteriore regressione mirata Programmatore/profili dopo l'allineamento del suo budget: 24 test OK.
- Controllo browser della vera interfaccia locale in modalità offline, desktop e 390×844: compositore visibile, suggerimenti senza invio, collegamenti presenti, nessun overflow orizzontale. Non è un test di inferenza reale. Il messaggio di backend non collegato nell'anteprima è atteso.

## Limiti e aggiornamento

Nessun deploy Debian, inferenza reale su desktop, accesso a documenti o credenziali produttivi. Il collaudo operativo deve verificare saluto senza strumenti, ricerca cliente, lettura documento grande con risposta finale, cambio manuale di modello, modello senza thinking/strumenti e cancellazione.

Gli estratti non sostituiscono un futuro lettore documentale con paginazione e ricerca per blocco cliente. Il trasporto del worker resta bufferizzato: il backend riceve la risposta al termine, non viene dichiarato streaming remoto. I controlli della chat non cambiano assegnazioni o policy; le scelte restano in Architettura/Macchine. CI GitHub del nuovo commit da controllare separatamente.
