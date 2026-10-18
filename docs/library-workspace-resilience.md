# Libreria IA: accesso condiviso e guasti recuperabili

La Libreria IA è lo spazio documentale principale di Cora. Gli agenti non devono
indovinare percorsi o cercare nel codice sorgente per trovarla. UI, strumenti e
diagnostica ora usano `library_workspace_root()` in `core/file_paths.py`.

## Perché la connessione era fragile

- Gli strumenti conservavano `KNOWLEDGE_ROOT` all’importazione del modulo;
  l’interfaccia invece risolveva la configurazione al momento della richiesta.
- Sul desktop la cartella predefinita era creata dal percorso UI: una richiesta
  in chat prima di aprire File poteva trovarla assente.
- La diagnostica componenti usava un percorso relativo alla directory di avvio,
  anziché la stessa base del resto del programma.
- Il preflight e l’elenco diretto verificavano un errore restituito come JSON,
  mentre l’adapter delle capability sollevava un’eccezione. L’errore del tool
  attraversava quindi `prepare` e faceva fallire tutta la chat.
- `os.walk` poteva ignorare un errore di accesso alla cartella, trasformandolo
  apparentemente in un elenco vuoto.

Questi sono difetti del codice riproducibili. Un messaggio “cartella non
disponibile” da un’installazione reale non permette da solo di distinguere
configurazione errata, directory assente e mount non collegato.

## Nuovo comportamento

La cartella desktop predefinita è inizializzata al primo accesso, anche agentico.
I percorsi relativi sono ancorati alla directory del progetto. Ogni nuova
operazione risolve la configurazione attuale; non resta legata al valore letto
quando il modulo Python è stato importato.

Un percorso configurato esplicitamente non viene mai creato automaticamente e
non è sostituito con un’altra libreria vuota: un mount mancante deve essere
visibile come guasto. Ripristinato il percorso, le nuove operazioni lo vedono
senza ricaricare il modulo. Una modifica del file `.env` richiede comunque il
riavvio del processo per caricare le nuove variabili d’ambiente.

Le categorie distinguono percorso invalido, root mancante, percorso non-directory,
accesso negato, storage irraggiungibile, radici sovrapposte, sottocartella mancante
e limite di scansione. Il codice viene conservato anche attraverso gli adapter
Supervisor → ricerca e compare negli eventi del tool. Nessun percorso assoluto
o messaggio grezzo dell’eccezione viene aggiunto alla diagnostica pubblica.

Il preflight e l’elenco diretto gestiscono gli errori delle capability e le
risposte malformate. Il primo passa al modello un limite esplicito: nessun
documento letto è confermato, nessuna affermazione che il documento non esista,
nessun retry automatico della stessa operazione nel turno. L’elenco diretto
restituisce una spiegazione all’utente senza chiamare il modello. Una libreria
vuota resta invece un risultato valido con zero documenti.

Cancellazione, timeout del run, perdita di durabilità ed effetti incerti non
diventano avvisi recuperabili. Le policy e i confini filesystem restano attivi;
nessun nuovo tool di scrittura, nessuna estensione alle radici del File Server.

`/health`, la diagnostica componenti e `python -m deploy.doctor` espongono lo
stato della Libreria e una categoria azionabile, senza elencarne i contenuti.

## Installazione e verifica

Installare la revisione aggiornata e riavviare il backend. Su deployment con
mount esplicito, verificare che `CORA_KNOWLEDGE_ROOT` indichi la cartella vista
dal processo/container API e che sia montata con i permessi del servizio.
Una cartella visibile soltanto al browser o al sistema host non è automaticamente
visibile al backend. Non creare una cartella vuota al posto di un mount perso.

I test riproducono accesso agentico prima della UI, percorsi aggiornati dopo
l’importazione, mount assente e ripristinato, permessi negati, storage guasto,
risposte malformate, elenco senza modello e grafo chat completo con root assente.
Verificano anche che cancellazioni e fallimenti critici continuino a propagarsi.
L’installazione sul server reale rimane distinta dai test di sviluppo.
