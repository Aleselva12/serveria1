# Checkpoint operativo: Serveria e Server Tele

Stato: preparazione dell'integrazione; **non** è un deploy o una certificazione di produzione.

## Decisioni

- Server Tele: repository separata `Aleselva12/magazzino-tele` (branch `master`), GUI desktop Tkinter, MySQL `magazzino_tele`.
- Serveria/Cora: frontend web, API e PostgreSQL propri. **Non** migrare tabelle MySQL in PostgreSQL e non collegare direttamente i rispettivi database.
- Prima integrazione: servizio MySQL **dedicato e isolato**, credenziali esterne al repository, volume persistente separato; nessuna porta pubblicata su Internet o LAN.
- La GUI Tkinter non funziona come pagina browser: per utilizzare Server Tele da telefono/PC remoto servirà un frontend web o un servizio API distinto, accessibile solo attraverso l'accesso privato Tailscale. Non presumere che basti un iframe.
- Cora potrà usare in futuro API tipizzate, con permessi separati per lettura e scrittura; mai accesso indiscriminato al database.

## Prima di importare dati reali

1. **Ruotare le credenziali MySQL**: nella repository pubblica di Server Tele esistono riferimenti a credenziali nei file di test/debug. Rimuovere i segreti dal codice e dalle copie di configurazione e valutare la cronologia Git; non ripetere valori nei log o nelle PR. Creare un utente applicativo con privilegi minimi, separato dall'account amministrativo.
2. Inventariare schema SQL, codice `backend/crud.py`, `backend/inventario_crud.py`, backup manager e tipologie di dati effettivamente in uso.
3. Eseguire un dump della sorgente MySQL con consistenza verificata e conservarlo offline prima di qualsiasi migrazione; verificare charset, tabelle, trigger, FK e record count.
4. Configurare `deploy/integrations/server-tele.mysql.yml` mediante segreti host non committati. Non avviare l'import su database di produzione esistente.
5. Verificare che il sistema di backup privato di Cora **non include automaticamente** il database MySQL di Server Tele, né i volumi esterni: prevedere un backup MySQL dedicato e una prova di restore prima dell'uso definitivo.
6. Integrare prima funzioni **read-only** (catalogo, disponibilità, ordini), quindi CRUD con controlli e conferme; esporre il servizio applicativo solo su Tailscale/reverse proxy configurato.
7. Non introdurre servizi in `compose.yml` principale fino alla verifica isolata. Nessuna cancellazione/sovrascrittura automatica degli originali.

## Stato altri punti del checkpoint

- P0.1: ripristino dinamico tool Libreria e test in branch, da confermare con CI.
- Prompt Supervisor legacy: rimosso dal branch; rimane `SUPERVISOR_BOOTSTRAP`.
- Backup dati Cora: infrastruttura già in `main`, **abilitazione host non effettuata**; seguire `docs/CONSOLIDAMENTO_20261018.md`.
- Gli step 8-12 e 15 della roadmap rimangono aperti: non marcarli come completi prima di implementazioni e verifiche.
- Stasera: collaudo reale e verifiche backup/restore isolato su Debian, senza dichiarare certificata una configurazione non ancora testata.

## Criteri per il primo rilascio Server Tele

- Schema e dati migrati senza perdita, conteggi e checksum documentati.
- Avvio/stop e healthcheck separati da Cora; nessuna porta MySQL esposta pubblicamente.
- Accesso remoto privato e autenticazione applicativa.
- Backup automatico MySQL cifrato e restore provato su volume/container vuoto.
- Compatibilità CRUD e concorrenza verificata con test non distruttivi.
- Rollback applicativo e dati documentati; nessuna migrazione irreversibile senza copia.
