# Priorità, Attività e stati della mappa — 6 novembre 2026

## Diagnosi e correzioni

Il messaggio precedente accorpava timeout, errori HTTP e connessioni interrotte: non consente di stabilire quale si sia verificato sul Debian senza i suoi log. Nel codice erano presenti un limite di 65 secondi, scaricamento del modello dopo ogni richiesta (keep_alive=0) e un budget fisso di 1500 token per un massimo di otto valutazioni. Queste impostazioni espongono a caricamenti ripetuti e risposte troncate. Ora: 180 secondi backend, 210 frontend, modello mantenuto per cinque minuti, generazione proporzionale al numero di obiettivi e contesto 12288. Il maggior contesto richiede più memoria; la disponibilità delle risorse va verificata sul server.

Errori distinti per timeout (504), risposta HTTP del provider e connessione interrotta. Nessun retry automatico. La causa dell'episodio originale rimane da confermare sul server reale.

Prima dell'inferenza viene creato un runtime_run con target roadmap_classifier, visibile nel registro condiviso Attività. Transizioni running/completed/failed, durata diagnostica, identità dichiarata dal provider ed errore sono registrati. Se il registro non è disponibile, la valutazione non parte. Gli errori non sostituiscono l'ultima valutazione positiva.

Il verde richiede almeno un E2E reale, commit attivo e ambiente Debian corrispondenti, tutti i controlli associati superati e sottoelementi verificati. Contratti, simulazioni e check HTTP da soli non certificano il funzionamento. Problemi noti prevalgono sul verde; miglioramenti previsti sono gialli; controlli parzialmente falliti e problemi dei figli sono arancioni. Rosso indica il fallimento di tutti i collaudi funzionali associati al perimetro del nodo, non un singolo check preliminare. Grigio indica obiettivo futuro o evidenza insufficiente. Non si eredita un successo dal genitore per certificare figli o fratelli privi di prove. Pianeti e lune nell'ispettore usano gli stessi colori della costellazione. La struttura resta invariata e non richiede modifiche alla repository qwe.

## Verifiche

- Frontend: 201 test superati; compilazione riuscita (avviso preesistente sulla dimensione dei bundle).
- Backend mirato: 33 test, 25 superati e 8 saltati perché richiedono PostgreSQL.
- Suite backend completa eseguita su Windows: vedere resoconto PR per gli errori di ambiente; non equivale a un collaudo Debian.
- Nessun collaudo reale del server, di Ollama remoto o di PostgreSQL produttivo eseguito.

## Verifica dopo installazione manuale

Sul Debian selezionare gli obiettivi e avviare Valuta priorità. Controllare in Attività il nuovo run, modello, durata ed eventuale dettaglio di errore. Ripetere a modello caldo. Eseguire i collaudi funzionali effettivi e verificare versione attiva, ambiente, associazioni puntuali e aggiornamento dei colori dopo il refresh. Non trasformare i successi simulati in attestazioni reali. Nessun merge o deploy automatico previsto da questa modifica.
