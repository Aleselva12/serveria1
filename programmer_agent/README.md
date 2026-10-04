# Programmatore Cora

Agente LangGraph nativo con modello Ollama (`CORA_MODEL_PROGRAMMER`, fallback globale), coda e lifecycle di Cora, tool governati e streaming SSE. È orientato alla creazione di tool e automazioni su richiesta. Non installa o attiva il codice prodotto.

## Utilizzo

In **Programma**, creare un workspace, selezionarlo e descrivere il componente nel Copilot. La pagina mostra sorgente, differenze, cronologia del workspace e verifiche. Le conversazioni sono salvate in PostgreSQL con identità `programmer_agent`; l'ID conversazione è l'ID workspace. Run e operazioni restano visibili in Attività, anche dopo un errore o un riavvio. Cambiare pagina interrompe soltanto la lettura dello stream: il lavoro prosegue nel backend e non viene ripetuto automaticamente. Il pulsante Ferma usa la cancellazione del runtime.

I workspace sono snapshot **filtrati**, non checkout Git completi: escludono dati, credenziali, file nascosti, link, dipendenze e file oltre 256 KB. Sono ammessi fino a 4.000 file e 12 MB per snapshot. Un controllo sha256 impedisce sovrascritture di file cambiati dopo la lettura. Le scritture sono limitate al workspace; non c'è endpoint di merge/deploy o caricamento dinamico di Python. La cartella predefinita è `data/programmer`; nel deployment Compose è `/state/programmer`, già inclusa nel volume persistente e nei backup dello stato.

Il Supervisor può delegare con `programmer_agent_tool(query, workspace_id)` quando l'utente fornisce un workspace esistente. Il Copilot chiama direttamente il programmatore senza un passaggio del Supervisor. La cronologia manuale nel Copilot viene recuperata dal database; le deleghe del Supervisor ricevono invece la richiesta delegata, come gli altri specialisti.

## Strumenti e skill

Quattordici capability: elenco, lettura, ricerca e scrittura di file; differenze; catalogo dei contratti reali; caricamento di skill e template; verifiche; interrogazione Graphify; validazione delle bozze grafiche; registro componenti, revisioni e pacchetti di consegna. Sono registrate nel catalogo Tools e nel permission engine. La scrittura di codice attivo e l'attivazione di componenti restano capability bloccate senza percorso eseguibile.

Le quattro skill sono risorse versionate di **Cora**, non skill installate in ChatGPT: creazione tool, creazione automazioni, verifica componenti e orientamento nel progetto. Il modello riceve soltanto descrizioni e carica le istruzioni quando necessarie. Template e skill sono nel repository e vengono inclusi nello snapshot.

Una bozza JSON compatibile può essere importata esplicitamente nella pagina Tools con **Importa bozza in Tools**. Il validatore è lo stesso dell'editor. Questa operazione non esegue, pianifica o assegna l'automazione; l'esecutore delle bozze resta un lavoro successivo. Anche un nuovo file Python rimane da revisionare e collegare manualmente a contratti, permessi e agenti.

## Verifiche

`syntax` analizza Python con AST e JSON con il parser, senza importare o eseguire il sorgente. Non prova correttezza dei tipi, build frontend, import o comportamento. I risultati sono salvati in `last_check.json`; la UI mostra il risultato della verifica avviata nella sessione.

`python_tests` esegue unittest in Docker. Preparare una volta l'immagine dalla radice:

```sh
docker build -f programmer_agent/checks.Dockerfile -t cora-programmer-checks:local .
```

Il container usa rete disabilitata, sorgente montato in sola lettura, filesystem di sola lettura, utente non privilegiato, limiti CPU/RAM/processi e nessuna credenziale o socket Docker. L'immagine contiene solo le dipendenze Python fissate in requirements-deploy.lock. Non si installano dipendenze durante la verifica e non si scarica automaticamente un'immagine mancante. Output e durata sono limitati. Cancellazione/timeout rimuovono il container; il runtime non rilascia il posto prima del ritorno del controllo. Non c'è fallback all'esecuzione sul sistema host.

Il backend deve poter chiamare il daemon Docker. Compose **non** monta automaticamente il socket nel backend: lettura, scrittura e controlli statici funzionano anche senza Docker. Se backend e daemon vedono percorsi diversi del medesimo stato, configurare `CORA_PROGRAMMER_DOCKER_WORKSPACE_ROOT` con il percorso lato daemon. Un'immagine mancante o Docker non disponibile viene segnalato come verifica non eseguita, non successo. Il runner non certifica la sicurezza di un componente né sostituisce una revisione.

## Graphify locale

La dipendenza è opzionale e separata dal core:

```sh
python -m pip install -r requirements-programmer-graph.txt
```

**Costruisci mappa Graphify** esegue la CLI fidata con `extract --code-only --no-cluster` sul baseline immutabile, in un output temporaneo nuovo: analisi sintattica del codice, nessun modello o backend cloud. Il job passa dalla coda comune. È anche possibile importare `graph.json` (nodi/edges o links); in questo caso l'utente dichiara che il grafo appartiene allo snapshot selezionato: non esiste una verifica crittografica indipendente della provenienza di un file esterno.

L'adapter espone ricerche di nodi e vicini con risultati limitati, preservando metadati EXTRACTED/INFERRED. I riferimenti a moduli senza definizione estratta diventano nodi esplicitamente non risolti, senza inventarne il contenuto. La mappa riguarda il baseline: dopo modifiche viene segnalata come obsoleta rispetto al workspace. Per una nuova baseline creare un nuovo workspace dopo l'integrazione delle modifiche. Non è una traccia runtime e non è la mappa del framework agentico mostrata in Architettura. La pagina Programma espone una vista SVG locale: ricerca di simboli, selezione e vicini, metadati e indicatori di inferenza/riferimenti non risolti. La vista è limitata a 40 nodi e 100 archi; non carica HTML esterno.

## Limiti della prima versione

Nessuna automodifica autonoma, applicazione al sorgente attivo, shell libera, installazione pacchetti da parte del modello, attivazione di tool generati. L'esploratore è un lettore paginato, non un IDE completo. La capacità reale del modello sul PC e il confronto fra motori vengono misurati successivamente; le verifiche automatiche del repository usano un modello simulato per provare il ciclo tool e non certificano la qualità del modello locale.


## Componenti e consegne

Il modello e l'utente possono registrare un componente (tool, automation, frontend o other) con file, test, dipendenze e istruzioni di integrazione. Ogni revisione incrementa la versione e azzera la revisione precedente. Il registro è nel workspace, fuori dai sorgenti generati. Anche le evidenze dei controlli sono fuori dai file che il modello può modificare.

Lo stato verificato richiede tutti i profili previsti: tool = syntax/contracts/python_tests; automation = syntax/contracts; frontend = typescript/frontend_build; other = syntax. Verificato significa che quei profili sono superati, non certifica la correttezza complessiva. I controlli si riferiscono al digest di tutto il workspace: anche una modifica a un altro file invalida conservativamente evidenze e stato della revisione. Un controllo fallito successivo prevale su quello riuscito dello stesso profilo.

L'utente può annotare revisione, integrazione avvenuta e attivazione avvenuta, in ordine e con una nota/evidenza. Queste sono dichiarazioni dell'utente: nessun codice viene applicato o eseguito dai pulsanti. Il modello non dispone di una capability per avanzare questi stati.

Prepara consegna crea uno ZIP immutabile con files/, changes.patch completa, manifest.json (hash, baseline, versione, esiti e controlli mancanti) e HANDOFF.md. Sono esportati soltanto i file dichiarati del componente. Si possono consegnare anche bozze non ancora verificate; i controlli mancanti sono espliciti. Dopo una modifica occorre registrare una nuova revisione. Le consegne precedenti restano scaricabili con autenticazione; massimo 100 per workspace.

## Controlli aggiuntivi

contracts usa AST per verificare dichiarazioni degli adapter generati (azioni, effetti, retry, tipi e identità), senza importarli. Le automazioni sono validate con lo schema dell'editor e una bozza incompleta non supera il profilo. Non sostituisce il controllo semantico dei tipi, la verifica dei permessi o il collegamento al runtime.

typescript esegue tsc; frontend_build esegue tsc e vite build sulla copia frontend del workspace in un container Node dedicato. Preparare l'immagine una volta:

```sh
docker build -f programmer_agent/frontend-checks.Dockerfile -t cora-programmer-frontend:local .
```

L'immagine installa il package-lock del repository fidato con npm ci --ignore-scripts. Le dipendenze restano nell'immagine: i controlli non installano pacchetti dal workspace né usano la rete. Il frontend è copiato in /tmp per scrivere output e cache. Isolamento come Python, con 1 GB RAM e tmpfs 256 MB; limite massimo 120 secondi. Gli hash di package.json e package-lock.json devono corrispondere ai manifest nell’immagine; una modifica alle dipendenze richiede preparare manualmente una nuova immagine. Configurazione Node: CORA_PROGRAMMER_FRONTEND_CHECK_IMAGE. L'esecuzione Docker reale va verificata sul deployment; i test del runner usano simulazioni nell'ambiente di sviluppo.
