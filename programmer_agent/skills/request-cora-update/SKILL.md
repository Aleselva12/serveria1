---
name: request-cora-update
description: Modificare Cora su richiesta del proprietario tramite Git, verifiche e servizio host di rilascio.
---
1. Richiede un workspace mode=git creato dall'utente e updater configurato. Gli snapshot sono bozze: non possono essere rilasciati.
2. Chiarisci la modifica richiesta. Leggi codice e contratti; modifica soltanto la copia. File privati e configurazione del servizio host non sono sorgenti del progetto.
3. Aggiungi test pertinenti e, per schema SQL, una nuova migrazione versionata; non riscrivere migrazioni già applicate.
4. Registra/consegna il componente se utile. Esegui controlli pertinenti. Salva programmer_git_commit e usa il commit esatto per programmer_prepare_release.
5. La preparazione restituisce un job asincrono. Non dichiarare successo o attivazione prima di consultarne lo stato. Se non è pronto riferisci ID e stato; evita polling continuo del modello.
6. Solo se l'utente richiede l'applicazione, usa programmer_apply_release con ID rilascio e commit esatto. La capability passa dall'approvazione generica. Non aggirare il servizio con una shell o import dinamici.
7. Il rilascio ferma Cora dopo la preparazione, crea backup e prova le migrazioni su un DB isolato; se fallisce recupera la versione precedente. Riprendi lo stato dopo il riavvio.
8. Un rollback richiesto ripristina ANCHE I DATI al backup precedente, conservando un backup separato dei dati attuali: chiarisci questo effetto e richiedi approvazione.
9. Aggiornamenti alla configurazione host/Compose e al servizio updater richiedono installazione separata del proprietario. Non attribuire queste modifiche a un rilascio applicativo.
