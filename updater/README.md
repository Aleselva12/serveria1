# Aggiornamenti richiesti dal proprietario

Il Programmatore può modificare il codice di Cora, salvare un commit Git locale, preparare immagini Docker e richiederne l'applicazione. L'updater è un servizio **separato sul server Debian**, installato fuori dal repository e da state: continua a lavorare quando Cora si ferma. Non genera proposte, non avvia lavori periodici e non decide cambiamenti. Esegue soltanto richieste salvate dal proprietario, incluse richieste già accettate prima di una disconnessione o di un riavvio del servizio.

## Una volta sul server

Richiede Python 3.12+, Git, Docker Engine e Compose v2. Installare prima manualmente la versione di Cora che contiene questo bridge, con il deployment descritto in deploy/README.md. Il commit indicato deve essere quello realmente installato. La configurazione base di Compose deve essere già quella approvata, con Cora e il suo database dedicato in funzione.

Dalla radice del checkout fidato:

```sh
python3 -m updater.setup --root /srv/cora-updater --active-commit COMMIT_COMPLETO_INSTALLATO --github-repository Aleselva12/serveria1
```

La directory deve essere nuova e scrivibile dall'utente host che eseguirà il servizio; deve stare fuori da codice e state. L'utente deve avere lo stesso UID del container Cora e accesso a Docker. Il setup conserva una copia Git bare, la configurazione Compose risolta, un token privato e una copia del software updater in installed/. Aggiunge il bridge a deploy.env senza mettere credenziali in Git.

Il listener predefinito è il gateway della rete Docker bridge, raggiungibile tramite host.docker.internal. Per una configurazione diversa usare --listen e --port; mantenere l'accesso limitato alla rete privata dei container. Il telefono non contatta direttamente l'updater: passa dal login Cora e dal normale accesso HTTPS/Tailscale.

Preparare l'unità systemd usando cora-updater.service.example: adattare User e percorsi, installarla in /etc/systemd/system/cora-updater.service e avviarla. Il comando del servizio è:

```sh
cd /srv/cora-updater/installed
python3 -m updater.service --root /srv/cora-updater
```

Poi ricreare API/web dal checkout fidato per caricare i valori nuovi di deploy.env:

```sh
python3 deploy/manage.py up
```

La prima installazione e l'avvio del servizio sono operazioni host: non vengono effettuati automaticamente dal modello. Il backend non riceve socket Docker, credenziali Git o accesso al checkout attivo. Il token del bridge resta nell'ambiente del backend, senza essere restituito al modello o al browser. Per evitare più worker, il servizio usa un lock di processo.

## Accesso GitHub sul server

Con --github-repository owner/repo il servizio usa SSH verso quel solo repository. Configurare una chiave SSH dell'utente systemd autorizzata in lettura/scrittura sulla repository, con host key github.com verificata e presente nel suo known_hosts. Credenziali e chiave restano sul server, fuori da state e codice; non inserirle in chat, deploy.env o nel workspace. Il servizio usa BatchMode: se l'accesso manca il job fallisce senza attendere input. La configurazione può omettere GitHub per un uso soltanto locale.

I nuovi workspace eseguono fetch; quelli esistenti mantengono la loro versione e i cambiamenti. La pubblicazione aggiorna soltanto il branch cora/UUID tramite fast-forward e verifica il commit remoto. Aprire il link restituito per creare/revisionare/integrare la PR in GitHub. Dopo il merge un nuovo workspace recupera main aggiornato. Il ripristino del server non riscrive la cronologia GitHub: per riportare anche main indietro usare una PR di revert. Un'interruzione durante il push può lasciare il commit già pubblicato; ripetere la pubblicazione dello stesso commit è sicuro, mentre un branch divergente viene rifiutato.

## Dal computer o dal telefono

1. Aprire Programma e creare **workspace Git**. Il servizio recupera il branch GitHub configurato (main predefinito). Crea un worktree completo dei sorgenti testuali della versione più avanzata fra branch remoto e versione attiva, purché le cronologie non divergano. In caso di divergenza richiede prima di integrare il branch su GitHub; non scarta modifiche. Il rilascio continua a essere legato alla versione attiva iniziale. Dati, credenziali, link e file binari non sono sorgenti aggiornabili; limiti 6000 file, 1 MB per file e 40 MB complessivi. Il servizio rifiuta il progetto se non può rappresentarlo completamente, senza omettere silenziosamente file versionati.
2. Chiedere la modifica al Copilot. Può intervenire su frontend, backend, grafi agentici, contratti, permessi, tool e automazioni, test e migrazioni. Può anche creare o eliminare file nella copia.
3. Salvare il commit Git e **preparare rilascio**. Immagini API/web vengono costruite dal commit immutabile, con frontend compilato e suite Python isolata senza credenziali o servizi di produzione. Le dipendenze pubbliche possono essere scaricate durante la build; non si usano modelli cloud. Il pulsante **Pubblica branch su GitHub** o il tool programmer_publish_release pubblica il commit verificato in cora/ID_WORKSPACE e restituisce il link per creare una PR. Non effettua force push né merge automatici; pubblicazione e installazione hanno esiti distinti.
4. Quando il job è ready, selezionare quel rilascio e richiederne l'applicazione. La pagina mostra il commit e richiede una conferma esplicita. Dal modello la capability apply_release usa le approvazioni generiche legate al payload esatto. Non c'è applicazione automatica dopo preparazione.
5. Il servizio ferma API/web, attende fino a 330 secondi, salva dump PostgreSQL e archivio state con checksum e prova le migrazioni su una copia temporanea del DB in una rete Docker interna. La copia non vede state o credenziali host e viene eliminata. Servono memoria/spazio per la copia: il profilo di prova ha 2 GB per PostgreSQL e tmpfs da 2 GB.
6. Avvia le immagini candidate senza rebuild/pull, attende healthcheck e controlla HTTP + accesso DB. Solo dopo successo registra la nuova versione attiva. Il frontend va ricaricato; la sessione può proseguire perché il DB è persistente. Durante il riavvio API/web non sono raggiungibili. I job rimangono nel servizio host e la pagina recupera lo stato al ritorno.

Un workspace con una baseline superata deve essere ricreato dalla versione attiva: nessun merge automatico di versioni concorrenti. Si ammette un solo job di aggiornamento per volta; codice nuovo nel workspace dopo il commit non modifica un candidato già preparato.

## Recupero

Se il candidato ha iniziato l'avvio e fallisce, il servizio ripristina database e state dal backup pre-rilascio e avvia gli ID immagine precedenti. Non usa semplicemente un vecchio tag su un database già migrato. I backup devono essere integri; l'archivio viene validato ed estratto separatamente prima di cancellare dati attivi. L'updater conserva config, Git, job e backup fuori da state e non viene sovrascritto dal ripristino.

Un ripristino richiesto dopo un rilascio riuscito riporta **codice e dati** al backup precedente. Prima conserva un altro backup dei dati attuali. È permesso soltanto per il rilascio attualmente attivo e richiede un'altra richiesta/conferma; non è un downgrade senza perdita delle modifiche successive ai dati.

Dopo un arresto improvviso il servizio recupera un'applicazione già richiesta in base alle fasi salvate. Preparazioni interrotte vengono marcate fallite, non rilanciate alla cieca. Un errore di recupero produce recovery_required e blocca nuovi rilasci. Se occorre intervento host: fermare il servizio, correggere Docker/spazio/permessi, consultare last-error.log privato, poi dalla directory installed eseguire:

```sh
python3 -m updater.recover --root /srv/cora-updater --job UUID_DEL_JOB
```

Il lock impedisce di recuperare mentre il servizio è ancora attivo. Riavviare poi il servizio. Non modificare a mano job/manifest per aggirare una verifica. Conservare spazio per backup, estrazione e immagini; non viene fatta pulizia automatica di Git, job o backup.

## Confini del rilascio

La configurazione host/Compose e il software updater installato restano fidati e separati. Una modifica a compose.yml viene rifiutata durante la preparazione: nuovi mount, porte, altri servizi o modifiche al controllore richiedono una revisione/installazione host distinta. Il normale rilascio può modificare l'intero codice applicativo, comprese architettura agentica e capacità del programmatore, ma non amministra altri servizi NAS né il sistema operativo.

Le migrazioni già applicate restano immutabili: aggiungerne nuove secondo database/migrations/README.md. Il backup riguarda il database dedicato Cora e state, non mount NAS esterni o modelli Ollama. Non eseguire altri processi che scrivano questi dati durante lo snapshot.

Le verifiche di codice e migrazioni non certificano la qualità del modello, la correttezza funzionale di ogni richiesta o l'assenza di errori semantici. Nel workspace di sviluppo Git/HTTP vengono provati realmente; operazioni Docker/deployment sono simulate. Il ciclo reale va collaudato su un'installazione sacrificabile prima del server personale.
