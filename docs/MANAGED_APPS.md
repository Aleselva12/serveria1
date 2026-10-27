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

## Migliorie stato/applicazione (ottobre 2026)

Il pannello ora distingue:
- Sorgenti clonate (`installed`).
- Configurazione locale presente (`configured`).
- Web Docker realmente avviato e healthy (`running`).
- Commit locale effettivamente estratto da Git.
- Job falliti o incompleti, con fase.

Il comando **Aggiorna e verifica** scarica soltanto il branch autorizzato e avvia il Compose
del servizio isolato con `--wait`; non segna completato un deployment il cui web non
diventi healthy. I container Cora e il database PostgreSQL non vengono toccati.

**Attenzione al servizio installato su serverale:** il percorso mostrato qui e
quello in `updater/README.md` sono esempi di due installazioni differenti, NON due percorsi
da aggiornare insieme. Prima di eseguire qualunque copia/restart sul Debian,
controllare in sola lettura `systemctl show cora-updater.service -p ExecStart -p WorkingDirectory`
e `systemctl cat cora-updater.service` (non pubblicare credenziali né token).
Usare soltanto il percorso effettivo dell'unità in uso; se non coincide,
NON eseguire i comandi d'esempio e ricostruire la procedura corretta.
Il merge di Serveria aggiorna i container Cora ma NON modifica la copia live di
`/srv/cora-tools/updater/installed/updater/managed_apps.py`.
Dopo il merge e l'aggiornamento Cora, prima di abilitare il nuovo comportamento
copiare il solo modulo con backup, verificando che il checkout della nuova versione
contenga il file. Esempio per un checkout Git aggiornato e fidato:

```bash
# Leggere questo comando prima di lanciarlo sul Debian
SRC=/home/ale/cora-update-candidate/updater/managed_apps.py
DST=/srv/cora-tools/updater/installed/updater/managed_apps.py
test -f "$SRC" || { echo 'Aggiorna prima il checkout candidato'; exit 1; }
python3 -m py_compile "$SRC"
cp -p "$DST" "$HOME/managed_apps.before-update.py"
cp "$SRC" "$DST"
sudo systemctl restart cora-updater
sudo systemctl is-active cora-updater
```

Non cambiare `config.json`, `bridge.token` né `compose.json`; non fare reset
del vecchio branch locale Cora. I volumi Magazzino Tele rimangono separati.

Nota: anche quando il codice host è aggiornato, una tabella MySQL mancante richiede
la procedura conservativa `deploy/reconcile_schema.py` nella repository Tele.
Il pulsante updater NON effettua migrazioni automatiche di database.
