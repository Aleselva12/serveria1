# Consolidamento del 18 ottobre 2026

Fonte canonica: [roadmap.json](roadmap.json), importata dalla Home. Rigenerare
`17 passi.txt` con `python deploy/render_roadmap.py` dopo ogni modifica.
Lo stesso comando genera la copia `frontend/src/data/roadmap.json` necessaria
alle build isolate Docker: i test ne verificano l’uguaglianza con la fonte.
Il documento allegato nella chat è stato consultato come fotografia storica;
il file aggiornato in repository è una nuova versione operativa, senza modificare
le fonti sincronizzate del progetto.

DB-01 è chiuso per causa utente su dichiarazione del proprietario. File server
agentico e sincronizzazione originali/IA attendono hardware. Permission finali
fuori scope, prompt separato. Attività 13 esclusa. Collaudi reali riuniti al 17;
il 16 prepara la baseline, che si congela soltanto dopo il collaudo.
I punti 1, 8–12 e 15 ancora aperti non sono dichiarati implementati da questa PR.

## Audit del codice e dei meccanismi esistenti

Audit statico, non inventario attestato del server live:

| Dati/meccanismo | Evidenza | Trattamento |
|---|---|---|
| Cronologia, run, memoria, approvazioni, Libreria metadati | PostgreSQL, `postgres_data:/var/lib/postgresql/data` | Dump logico `pg_dump -Fc`, controllo `pg_restore --list` |
| Libreria IA, originali, allegati, audio, trascrizioni, upload, workspace, Gmail e impostazioni | Bind `/state` in compose.yml | Archivio completo a scrittori Cora fermi |
| Configurazione effettiva e segreti interpolati | Updater `compose.json`, `config.json`, `bridge.token`, `current.json` | Dentro il backup cifrato; mai nei branch Git |
| Eventuali file privati aggiuntivi | Non deducibili dal solo repository | Elenco host `data_backups.private_files`, file regolari assoluti |
| NAS `/nas/drive`, eventuale `/host`, modelli Ollama | Mount esterni / servizio esterno | Esclusi: inventariati nell’audit, politica separata |
| Backup manuale preesistente | deploy/manage.py, formato 1 | DB + state + deploy.env, checksum, restore solo su target vuoto |
| Backup pre-rilascio | updater/engine.py, job/backup | Rimangono distinti, necessari al rollback; nessuna retention nuova li tocca |

Tutti i percorsi assoluti negli esempi seguenti sono generici e vanno sostituiti sul proprio host. Nessun inventario del server reale è pubblicato qui.

Tutti i percorsi assoluti negli esempi seguenti sono generici e vanno sostituiti sul proprio host. Nessun inventario del server reale è pubblicato qui.

Non è sicuro usare il vecchio Compose del checkout mentre l’updater governa
immagini e mount. La pianificazione nuova è eseguita dallo stesso worker host,
sotto lo stesso lock dei job, usando il Compose risolto e gli ID immagine attivi.
Aggiornamenti e backup non possono sovrapporsi nel processo updater.
Non avviare contemporaneamente altri strumenti host che modificano i dati.

## Snapshot codice GitHub

`code-snapshots.yml` conserva al massimo un checkpoint al giorno, oppure uno
avviato manualmente, se il commit non è già conservato. Crea un nuovo branch
`snapshots/<UTC>-<sha>` puntando al commit già pubblicato su **main**. Nessun
commit, reset, force-push, merge o sostituzione di main. Nessun contenuto nuovo
viene letto dal filesystem o inviato a GitHub. Token effimero limitato al job.

La repository è pubblica. Per questo non si esegue `git add .` né si pubblicano
automaticamente workspace o file non revisionati. Le modifiche locali devono
prima essere committate e pubblicate con il percorso release/PR già esistente.
Lo snapshot protegge revisioni pubblicate, non le bozze locali; i workspace
privati sono compresi in `/state`. GitHub non è una copia indipendente del
servizio GitHub: l’eliminazione della repository perderebbe anche questi branch.
Nessuna cancellazione automatica dei branch snapshot.
La pianificazione diventa attiva dopo il merge del workflow sul branch predefinito;
GitHub può ritardare le esecuzioni pianificate. Riferimenti:
[eventi GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
e [comandi age](https://github.com/FiloSottile/age).

## Installazione e attivazione backup sul server

Il backup non è abilitato di default. Non sono disponibili in questa sessione
accesso SSH/Tailscale, chiave age o inventario attuale dei mount: nessuna
installazione o esecuzione sul server è attestata da questa PR.

1. Aggiornare manualmente la copia installata del pacchetto updater con questa
   versione, conservando config, token, repo.git e job. Il normale aggiornamento
   Cora non sostituisce l’updater host. Seguire updater/README.md; fermare il
   servizio prima della sostituzione del pacchetto, poi riavviarlo.
2. Installare `age` sul server. Generare/conservare la chiave privata di recupero
   fuori dalla directory backup e mantenerne una copia offline. Il servizio di
   backup riceve soltanto il destinatario pubblico `age1…`.
3. Dalla directory `installed` eseguire:

   ```sh
   python3 -m updater.data_backups audit --root /opt/example-cora/control
   ```

   L’output contiene percorsi privati ma nessun ambiente Docker. Verificare
   `/state`, volume PostgreSQL e tutti i mount esclusi. Inventariare segreti fuori
   state, deploy.env originale ed eventuali override/config di altri servizi;
   inserire i file privati necessari in `private_files`. Non pubblicare l’audit.
4. Preparare una destinazione fuori da state, updater e checkout, su disco con
   spazio per almeno due copie temporanee oltre alla retention. Directory del
   proprietario del servizio, permessi 0700; consigliato filesystem cifrato per
   proteggere anche i temporanei. I temporanei sono privati ma in chiaro durante
   il backup. Un crash può lasciarli: ispezionarli e rimuoverli manualmente solo
   a servizio fermo; la retention non li cancella alla cieca.
5. A servizio fermo aggiungere a `config.json` la sezione seguente, con valori
   reali e hash dell’audit appena verificato, poi riavviare:

   ```json
   {"data_backups": {
     "enabled": true,
     "destination": "/opt/example-cora/backups",
     "age_recipient": "age1<destinatario-pubblico-reale>",
     "audit_sha256": "<hash-audit-reale>",
     "interval_seconds": 86400,
     "keep": 7,
     "private_files": ["/opt/example-cora/app/deploy.env"]
   }}
   ```

Il primo backup parte quando il worker è libero; i successivi dopo l’intervallo
dall’ultimo tentativo (minimo un’ora). I servizi API/web si fermano durante dump,
archiviazione e cifratura: scegliere una finestra compatibile con il primo avvio
e con la durata misurata. Non è un backup online senza interruzioni. External
writer su DB/state devono essere fermati separatamente. Al cambio dei mount o
del Compose l’hash non coincide e il backup fallisce prima di fermare Cora.

Controllare `data-backup-status.json` sul server: completed, failed e tipo errore.
Il codice non invia notifiche esterne. Una mancata ripartenza conserva il marker
con gli ID immagine e arresta il worker; il riavvio del servizio recupera quelle
immagini prima di nuovi job. Nessun ripristino dati viene fatto automaticamente.

La retention tiene gli ultimi 7 archivi completi con checksum valido e opera
soltanto dopo nuovo backup riuscito e servizi sani. Archivi incompleti o corrotti
non vengono contati né eliminati; vanno ispezionati. L’archivio age è autenticato;
il checksum esterno rileva danni, non sostituisce la verifica di decifratura.
`pg_restore --list` controlla il formato, non certifica un restore SQL completo.

## Recupero e verifica al punto 17

Decifrare sempre in una **directory nuova**, fuori dal server attivo:

```sh
python3 -m updater.data_backups unpack \
  --snapshot /opt/example-cora/backups/cora-<snapshot> \
  --destination /opt/example-cora/recovery-new \
  --identity /percorso/offline/identity.age
```

Verifica checksum esterno, autenticazione age, nomi/tipi dei file, checksum
interni e sicurezza dell’archivio state. Non importa DB e non ripristina segreti
automaticamente. Se fallisce, la directory privata rimane per diagnosi e non
va riutilizzata come backup valido. I link/file speciali in state sono rifiutati
per il restore automatico: recupero manuale isolato se necessario.

Per il restore completo usare un checkout della revisione salvata, un nuovo
progetto Compose e volume PostgreSQL dedicato, una directory state vuota e porte
diverse. Preparare deploy.env del target con credenziali e mount del **nuovo**
ambiente; controllare che nessun percorso/volume punti alla produzione. Dalla
nuova installazione:

```sh
python3 deploy/manage.py verify-backup /opt/example-cora/recovery-new
python3 deploy/manage.py restore /opt/example-cora/recovery-new
python3 deploy/manage.py up
```

Aggiungere gli override del **target** con `--compose-file` a ogni comando se
necessari. Il restore rifiuta DB non vuoto e state contenente file/link, importa
con `--exit-on-error`, revoca le sessioni e lascia l’avvio esplicito. Nessun
fallback automatico sulla produzione. I config salvati servono da riferimento;
non usare direttamente il compose.json ripristinato che contiene mount originali.
I file aggiuntivi stanno in `private-files.tar.gz` e vanno riposizionati e
protetti manualmente, dopo verifica della destinazione e dei segreti.

Al punto 17 verificare login nuovo, cronologia e allegati, lettura di un documento
Libreria IA noto, conteggi/hash scelti prima del backup, sessioni precedenti
revocate, updater/rollback e commit/immagini attivi. Registrare snapshot, revisione,
data, esito e tempo di recupero. Provare separatamente il restore NAS. Finché
questa prova non passa, il backup è implementato ma non certificato sul server.

Un backup sullo stesso server protegge da cancellazioni/errori applicativi,
non dal guasto/perdita dell’intero server: predisporre una seconda copia cifrata
su supporto separato nel percorso operativo successivo.

## Storico privato delle consultazioni

Migrazione 0003 additiva: eventi associati alla conversazione con cancellazione
in cascata. Registra gli esiti reali delle capability governate (anche pending,
error e uncertain), i file letti con successo dalla Libreria, gli estratti degli
allegati inclusi e le Context Pages incluse/preload. Non registra argomenti,
query, contenuti dei documenti o testo del ragionamento. I file letti durante
una scansione di ricerca sono letture del software, non prova che il modello
abbia ricevuto tutto il contenuto o l’abbia usato correttamente.

Endpoint autenticato, solo proprietario come gli altri endpoint chat, paginazione
per cursore e finestra ragionamento aggiornata durante il run. Lo storico dura
quanto la conversazione e viene incluso nel dump DB. Gli eventi precedenti
all’aggiornamento non vengono inventati. Il ragionamento del modello rimane
separato, transitorio e non certifica azioni. Errori di registrazione non causano
retry dei tool e sono segnalati dal contatore dall’avvio: nessuna pretesa di
completezza assoluta. Ricerca indicizzata/OCR rimangono attività distinte.

## Verifiche di sviluppo

- Build TypeScript/Vite riuscita; 104 test frontend superati, inclusi storico,
  paginazione, errore esplicito e isolamento delle risposte fra conversazioni.
- Suite backend mirata esistente: 52 test, 35 passati e 17 saltati per requisiti
  Linux/PostgreSQL/symlink. Nuovi test: 11, 9 passati e 2 richiesti in CI
  (PostgreSQL e age reale).
- Suite backend completa su Windows: 418 test, 4 failure, 8 errori, 86 skip.
  Le categorie riguardano symlink non autorizzati, permessi POSIX e differenze di
  percorsi/lunghezza nomi; riprodotti anche su main originale i casi file_extras,
  permessi audit_closure, nome lungo e override Tailscale. Non è dichiarata verde
  la suite completa locale. La CI Linux deve completare le verifiche restanti.
- CI estesa con age reale, prova chiave errata, storico PostgreSQL con isolamento
  e cancellazione in cascata. Deployment CI esteso con backup cifrato reale,
  decifratura, verifica del file state e import del dump in PostgreSQL isolato.

Queste verifiche non attestano installazione o collaudo sul server del proprietario.
