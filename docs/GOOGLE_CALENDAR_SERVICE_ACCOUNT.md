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
