# Google Calendar con Service Account (Cora, uso personale)

Questo metodo funziona con un calendario esplicitamente condiviso con l'indirizzo `client_email` del Service Account. **Non** usare `primary`: per il Service Account significa il suo calendario principale, non quello del tuo Gmail.

## Prerequisiti
- Google Calendar API abilitata nel progetto Google Cloud.
- Il calendario desiderato condiviso in Google Calendar con il Service Account e permesso **Apportare modifiche agli eventi**.
- File privato già sul server: `/srv/cora-secrets/cora-calendar.json`. Non copiare il JSON in chat, log o repository.
- Se Cora gira in Docker, il container deve poter leggere il file con i suoi UID/GID effettivi; il bind è read-only.

## Recuperare l'ID del calendario
Da Google Calendar → Impostazioni → seleziona il calendario condiviso → **Integra calendario** → **ID calendario**. Copia l'ID ESATTO (per il calendario principale personale è spesso un indirizzo Gmail). Non usare la parola `primary`.

## Attivare sul server (dalla cartella di deploy di Cora)
1. Accertati che il JSON sia leggibile dall'UID del servizio API senza modificarne il contenuto o divulgarlo. Con `CORA_UID=1000` spesso coincide con l'utente `ale`.
2. Aggiungi a `deploy.env` (privato, non versionato):

   `CORA_GOOGLE_CALENDAR_ID=ID_ESATTO_DEL_CALENDARIO`

3. Controlla la configurazione senza avviare il servizio:

   `docker compose --env-file deploy.env -f compose.yml -f compose.calendar-service-account.yml config --quiet`

4. Il comando di avvio richiede **entrambi** i file Compose e l'env-file:

   `docker compose --env-file deploy.env -f compose.yml -f compose.calendar-service-account.yml up -d --no-deps api`

   **Attenzione**: usare in futuro solo `compose.yml` durante deploy/upgrade rimuove il mount. Integrare l'override anche nel sistema updater prima di considerare la modifica permanente. Evitare di eseguire il comando senza aver verificato gestione updater/rollback.

5. Verifica con pagina Calendario → connessione, poi **solo lettura** su un intervallo conosciuto. Crea un evento di prova esclusivamente dopo aver controllato ID calendario e permessi.

## Sicurezza e comportamento
- Modalità Service Account attiva solo se è impostata la variabile `CORA_GOOGLE_CALENDAR_SERVICE_ACCOUNT_PATH` (dall'override Docker); altrimenti rimane OAuth.
- Il vecchio token OAuth non viene cancellato; non c'è fallback automatico su di esso se il file tecnico manca.
- L'identità del provider per le approvazioni include account di servizio e ID calendario, così un cambio di destinazione invalida le proposte non più corrispondenti.
- Non è possibile garantire le stesse funzioni degli account Google personali: gli invitati e alcune tipologie di eventi richiedono privilegi differenti.
- Nessun login Gmail o Google Workspace è necessario per questo metodo, ma la condivisione effettiva può essere limitata dalle impostazioni di Google.

## Ripristinare OAuth
Rimuovi l'override Compose dal set di file di deploy e ricrea **solo** il container API; il token OAuth precedentemente salvato rimane disponibile. Prima di farlo, verifica il sistema di aggiornamento del server.


## Updater persistente (server Debian gia installato)

L'updater usa `/srv/cora-tools/updater/compose.json` come **snapshot host**; gli aggiornamenti e i rollback ordinari conservano questo snapshot, i bind e le variabili Calendar. Il file `deploy.env` non viene letto a ogni rilascio. Non modificare lo snapshot a mano.

Per riconciliare in modo ripetibile uno snapshot esistente con la configurazione Calendar, usare **sull'host**, da una checkout aggiornata della repository:

```bash
cd /srv/cora-server-test
python3 -m deploy.calendar_service_account_updater \
  --updater-root /srv/cora-tools/updater \
  --deploy-env /srv/cora-server-test/deploy.env \
  --key /srv/cora-secrets/cora-calendar.json
```

Il comando precedente verifica soltanto, senza scrivere. Controllare che `CORA_GOOGLE_CALENDAR_ID` sia l'**ID calendario** (per un calendario personale, spesso l'email proprietaria), **non** un URL `calendar.google.com/calendar/embed`. Non condividere mai il JSON del Service Account.

Per applicare **solo quando occorre installare o riconciliare lo snapshot**:

1. Accertarsi che non ci siano job in esecuzione o in recupero, e che l'API corrente sia stabile.
2. `sudo systemctl stop cora-updater.service`
3. Ripetere il comando di verifica con `--apply`: valida la configurazione Docker, salva un backup `compose.before-calendar-*.json`, cambia solo `services.api.environment` e il mount della chiave read-only. Non ricrea alcun container.
4. `sudo systemctl start cora-updater.service` anche se l'operazione ha fallito; verificare `systemctl is-active cora-updater.service`.
5. Se lo snapshot e cambiato, verificare `docker compose -p cora -f /srv/cora-tools/updater/compose.json -f /srv/cora-tools/updater/images.json config --quiet`, quindi ricreare **solo** l'API con `up -d --no-deps --no-build api`. Conservare `images.json` (contiene l'immagine registrata dall'updater).
6. Verificare `docker exec cora-api-1 python -c 'from core import google_calendar; print(google_calendar.status())'`, poi lettura eventi e scrittura di un appuntamento di prova con autorizzazione utente.

La funzione e idempotente; se lo snapshot e gia corretto non lo riscrive. Il backup dello snapshot potrebbe contenere segreti del deploy: resta sul server con permessi 600 e non deve entrare in GitHub. Il comando non legge la chiave dentro la repository e non crea copie delle credenziali.

**Reinstallazione dell'updater**: durante `python -m updater.setup`, includere anche `--compose-file compose.calendar-service-account.yml` e le eventuali altre sovrascritture Compose gia usate sul server (es. mount NAS e terminale). L'override Calendar va passato **alla creazione** dello snapshot; aggiungerlo alla repository non modifica una installazione esistente. Non reinizializzare l'updater attivo soltanto per Calendar.

**Rollback**: i normali rollback dell'updater usano il medesimo snapshot persistente. Se serve annullare specificamente questa configurazione host, farlo durante una finestra di manutenzione ripristinando il backup con updater fermo, poi ricreare la sola API. Non annullare modifiche host piu recenti sovrascrivendo uno snapshot successivo.

> In caso di modifica del codice di autenticazione, effettuare una verifica compatibilita prima di aggiornare: il snapshot puo essere persistente ma una versione API precedente potrebbe non riconoscere queste variabili.
