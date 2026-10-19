# Gestione applicazioni esterne dalla Home

Il pulsante **Gestisci applicazioni**, accanto a **Aggiorna Cora**, mostra un catalogo fisso di servizi Debian. Prima applicazione: `magazzino-tele`, repository `Aleselva12/magazzino-tele`. Nessun collegamento agli agenti IA e nessun accesso ai suoi dati da Cora.

## Architettura

- Browser → backend proprietario Cora → bridge autenticato → host updater.
- L'host updater ha allowlist **statica**, non accetta URL Git, percorsi o Compose dal browser.
- Per impostazione predefinita **disabilitato**: configurare in `/srv/cora-updater/config.json` la chiave `"managed_apps_enabled": true` solo dopo aver aggiornato la copia installata dell'updater.
- La directory padre `/srv/apps` deve essere predisposta dall'amministratore sul Debian.
- L'installazione clona i sorgenti, ma non avvia la web app fino alla presenza di `deploy/.env` e `deploy/init/01-schema.sql` preparati sul Debian. Mai pubblicare chiavi o copie del database su GitHub.
- L'aggiornamento applica solo fast-forward Git sul branch approvato e ricostruisce il Compose specifico; non gestisce migrazioni del database. Eseguire backup MySQL e verificare compatibilità delle migrazioni prima dell'aggiornamento di un gestionale in produzione.
- Il catalogo punta al branch `master` di Magazzino Tele: prima dell'installazione, integrare nella sua repository il servizio web e la configurazione Docker. Se ancora presente soltanto sul branch della PR, l'installazione non riuscirà e la versione rimarrà disabilitata.
- Indirizzo Tele previsto: `http://100.112.253.3:8082`, raggiungibile solo dai dispositivi ammessi tramite Tailscale. Il web server non richiede login, ma MySQL richiede credenziali tecniche, e le ACL Tailscale devono limitare gli accessi.
- Il servizio Cora updater conserva autorizzazioni host elevate: non esporre direttamente la sua API o il suo token sulla tailnet.
- **Nessuna attivazione reale attestata**. Per prima cosa installare manualmente l'updater aggiornato (vedi `updater/README.md`), configurare il servizio e testare su Debian.

## Stato e limitazioni prima dell'uso quotidiano

Il gestore consente lo stato installato e la richiesta di installazione/aggiornamento da UI, ma non include un restore MySQL, un diff delle migrazioni né un rollback autonomo di Tele. Il job vive in memoria del processo host; dopo un suo riavvio lo stato storico potrebbe non comparire. Lo stato `needs_configuration` significa soltanto repository clonato: non significa programma installato e raggiungibile. Per il momento non registrare Magazzino Tele come servizio certificato finché la UI web, import Excel e restore non sono verificati.

Se il backend restituisce `available: false`, verificare installazione host, configurazione e token bridge senza aggiungere privilegi ai container Cora.
