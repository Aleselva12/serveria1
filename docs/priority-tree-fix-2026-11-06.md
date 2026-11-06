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

## Follow-up: classificatore a 180 secondi e provenienza collaudi

Le prove reali del 6 novembre mostrano una chiamata `roadmap_classifier` fallita dopo 180,29 s con HTTPException; la durata coincide con il timeout backend di 180 s. Non è provato che il problema risieda esclusivamente nel budget di generazione: occorre una nuova prova sul Debian con diagnostica Ollama. Per ridurre il carico della richiesta su CPU sono stati abbassati `num_ctx` da 12288 a 4096 e `num_predict` da `350*n+200` a `105*n+120`, chiedendo spiegazioni più brevi e conservando la validazione rigorosa degli otto ID. Il modello rimane configurabile tramite `CORA_ROADMAP_CLASSIFIER_MODEL`, non si introduce un fallback silenzioso e il timeout rimane esplicito. Il budget ridotto può provocare risposte incomplete: in tal caso la valutazione continua a fallire senza salvare risultati inventati.

I controlli mostrano `commit non disponibile` in diverse schede, anche quando il sito conosce l'ultimo commit installato. Il backend ottiene la revisione dal marker `.cora-revision` inserito nella **build dell'immagine API** dall'updater (`CORA_GIT_COMMIT`), non dal puntatore del frontend. Non è sicuro copiare il commit dichiarato dall'updater nelle evidenze di test: potrebbero riferirsi a un'altra immagine. La UI espone ora un messaggio di diagnosi quando un test collegato non ha uno SHA; serve verificare la build API, poi ripetere i controlli. Nessuna attestazione verde viene costruita da SHA mancanti, simulazioni, contratti o soli controlli HTTP.

Questo follow-up è una mitigazione del carico e un miglioramento diagnostico, **non** una certificazione dell'inferenza o una riparazione completa della provenienza dei collaudi. Necessari test su immagine Debian installata, una valutazione completa con il modello locale e verifica dell'identità SHA nelle prove persistite.

## Follow-up definitivo sul branch: timeout a 7 minuti e identificazione runtime

Su richiesta dell'utente, il timeout Ollama backend è **420 secondi**; il browser consente **450 secondi** (buffer per rete e persistenza) e il proxy Nginx **480 secondi**. Il browser riporta esplicitamente l'abort. La diagnosi del run fallito dopo 180 secondi resta valida per la release precedente, non prova una riuscita con il nuovo limite.

La risposta della health dashboard espone ora `runtimeCommit` ottenuto dalla revisione incorporata nell'immagine API in esecuzione, mentre la mappa legge separatamente `active_commit` dell'updater. **Quando il backend espone runtimeCommit, lo stato verde/rosso attribuito a un commit è calcolabile soltanto se i due SHA coincidono**, e ciascuna prova possiede lo stesso SHA e l'ambiente Debian corretto. In caso di disallineamento la scheda indica le due revisioni e impedisce una certificazione riferita a un'altra immagine. I test senza SHA restano non attribuiti: nessun pass inventato. In un backend precedente che non espone ancora runtimeCommit rimane il controllo conservativo degli SHA di ogni prova; il deploy del nuovo codice abilita il confronto forte.

Dopo il merge occorre un rilascio API+frontend con l'updater, una nuova valutazione reale e un nuovo collaudo. Il verde continua a richiedere un vero E2E, non preflight, contratto o simulazione. Nessuna garanzia di inferenza reale è deducibile dai soli test CI.
