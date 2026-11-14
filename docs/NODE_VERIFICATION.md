# Verifica automatica dei nodi

La Roadmap legge il registro salute esistente. Non esegue test al caricamento.
I pulsanti sopra la mappa filtrano le stelle per colore e mostrano i conteggi
globali. Le etichette sono presenti anche nei tooltip e per gli screen reader.
L'esportazione JSON comprende commit attivo, colori e risultati osservati.

- **Verde**: verifica del perimetro specifico. Può derivare da controlli del catalogo
  sulla versione attiva del Debian **oppure** da un'osservazione manuale datata
  e circoscritta, mostrata esplicitamente nel nodo. Una prova manuale NON
  diventa un E2E del catalogo e non certifica il commit installato.
- **Rosso**: almeno un controllo associato fallito sul Debian e sul commit attivo.
  Prevale sulle priorità statiche del nodo e sulle note di lavoro.
- **Arancione**: prove ancora incomplete e problemi documentati; non è un test fallito.
- **Giallo**: lavoro futuro previsto.
- **Grigio**: prove insufficienti, obiettivo non implementato oppure nodo
  ancora non collaudato. Non è un guasto (e non va conteggiato tra gli errori).
  Risultati CI/locali non certificano il Debian.
- **Giallo** comprende rifiniture di worker e fallback, miglioramenti e upgrade
  hardware previsti: questi ultimi non devono diventare guasti senza un fallimento
  reale dimostrato.

Le osservazioni del proprietario registrate nella snapshot della Roadmap
hanno il tipo `manual_pass` o `manual_followup`, data e perimetro descrittivo.
Non si assegnano automaticamente a tutti i figli o a un'intera stella: i parent
rimangono parziali quando mancano altre prove. Un `fail` attuale del registro
ha precedenza su un precedente verde manuale. Nessun test modifica la gerarchia
dell'albero, gli ID o le priorità deliberate dall'utente.

I controlli periodici scadono dopo 10 minuti; gli altri dopo 24 ore.
Il verde certifica esclusivamente il perimetro descritto dai controlli: ad esempio,
la prova worker verifica macchina e modello, non utilizzo GPU o prestazioni attese.
Le note dei problemi restano visibili, ma non bloccano il verde dei controlli associati.
Il verde indica il superamento di quei controlli, non la realizzazione di ogni obiettivo futuro.

## Uso dal sito: una esecuzione per clic

Dopo il primo rilascio dell'applicazione, aprire la Roadmap e premere
**Avvia collaudi una tantum**. Il server esegue in sequenza tutti i controlli
registrati che hanno un runner: preflight e test funzionali. Il sito mostra il
conteggio dei controlli completati, quello attualmente in esecuzione, gli esiti
puntuali e i controlli ancora da implementare. I nuovi esiti aggiornano i colori
senza aspettare il completamento dell'intera suite.

Non occorre caricare ZIP, copiare file o installare un timer. Non si avvia alcun
collaudo aprendo la pagina: l'esecuzione parte esclusivamente con il pulsante.
Chiudere il browser non ferma il job. Tornando nella Roadmap vengono recuperati
l'ultima esecuzione e il suo avanzamento dal database del server.

Il menu facoltativo delle destinazioni permette di scegliere desktop e laptop
fra le macchine gia registrate. Le selezioni dell'ultima esecuzione si ritrovano
riaprendo la pagina. Il modello e l'abilitazione restano quelli scelti in Macchine.
Il backend non riceve URL, comandi di shell o percorsi di file dal pulsante.

Il sito impedisce doppie partenze; una lock PostgreSQL impedisce sovrapposizioni
anche tra processi API diversi e CLI. Dopo un riavvio del backend un job rimasto
in esecuzione viene mostrato come interrotto, con gli esiti gia registrati conservati.
I controlli mancanti o senza prerequisiti non diventano mai verdi.

L'API e protetta dall'accesso proprietario e dall'autenticazione del sito:
`GET /api/v1/system/node-verification` legge lo stato e il catalogo disponibile;
`POST` sullo stesso percorso avvia una sola suite in background e restituisce 202.
La migrazione `0009_node_verification_runs.sql` viene applicata dal normale rilascio,
insieme alle altre migrazioni: non richiede file inseriti manualmente nel server.

## Manutenzione

L'interfaccia riceve dal backend l'elenco dei controlli eseguibili, senza duplicarlo
nel pulsante. Aggiungere un runner nel catalogo backend lo rende disponibile al sito
con il normale rilascio del codice. Non esiste un pulsante che possa validare nuove
funzioni senza prima definirne e implementarne i test: quel codice andra aggiornato
quando cambieranno i processi. Il pannello e il meccanismo di avvio restano generici.

## Copertura e configurazione

| ID | Verifica | Prerequisiti |
| --- | --- | --- |
| `memory_e2e` | Scrittura applicativa e lettura lessicale da un nuovo processo; pulizia della memoria sintetica | Database applicativo esistente |
| `calendar_e2e` | Scrittura Google confermata con rilettura | Uso normale dal sito, oppure account **di test separato** per la suite |
| `desktop_e2e` | API → worker selezionato → inferenza campione, modello effettivamente restituito e completamento | `CORA_VERIFY_DESKTOP_ID` |
| `laptop_e2e` | Come desktop, con destinazione indipendente | `CORA_VERIFY_LAPTOP_ID` |
| `memory_regression` | Budget del contesto e contratti | Test isolati, nessun modello |
| `calendar_regression` | Provider, revisioni e approvazioni | Provider simulato, nessun evento reale |
| `orchestration_regression` | Coordinator e decisioni sugli errori | Test isolati |
| `files_regression` | Upload/download sintetici, modifica, conflitti, permessi e ripristino | Directory temporanee |

Le regressioni sono di tipo `synthetic`, non E2E. Test saltati rendono il gruppo
incompleto. I test PostgreSQL distruttivi della suite CI non sono inclusi nel runner.
La memoria non prova embeddings, isolamento delle conversazioni o riavvio completo
del servizio. Il collaudo Google non prova il percorso di approvazione UI; questo ha
regressioni separate. I controlli già presenti per chat, file/NAS, backup e rollback
restano da eseguire/implementare: non ricevono esiti inventati da questa suite.

Gli ID macchina sono quelli registrati nella pagina Macchine. Impostarli nel
`deploy.env` del backend, con worker abilitato e modello selezionato dal proprietario.
Il runner non accende worker disabilitati e non cambia modello. Desktop e laptop
richiedono il worker aggiornato, che restituisce `actual_model` e `done`; un worker
precedente rimane non verificato. Non si deduce la GPU dal solo successo dell'inferenza.

Per Google configurare nel backend:

```dotenv
CORA_VERIFY_CALENDAR_TEST_ACCOUNT=yes
CORA_VERIFY_CALENDAR_TOKEN_PATH=/state/google-calendar-test/token.json
```

Il token deve appartenere a un account riservato al collaudo; il suo calendario
primario deve essere di prova. Il runner rifiuta il percorso del token di produzione,
non riutilizza le credenziali di produzione in assenza di configurazione e disabilita
gli invii di aggiornamenti agli invitati. Le fixture hanno UUID indipendenti, vengono
pulite anche dopo timeout/errori, e la mancata pulizia fa fallire il controllo.
L'ID da recuperare viene indicato nell'esito, senza contenuti utente o credenziali.

## Commit e ambiente

L'updater passa lo SHA del sorgente a `docker build`; il Dockerfile lo salva
nell'immagine, in `.cora-revision`. Runner periodico e suite usano questa identità,
senza attribuire al codice un commit preso dal puntatore dell'updater.
Le vecchie immagini senza identità restano non verificate fino al nuovo rilascio.
Per build Docker esterne all'updater passare esplicitamente
`--build-arg CORA_GIT_COMMIT=<SHA completo del sorgente>`.
Una checkout modificata non viene certificata come HEAD.

## Diagnostica facoltativa per manutentori

La CLI rimane disponibile, ma non e necessaria per l'uso dal sito:

```sh
docker compose --env-file deploy.env exec -T api python -u -m deploy.verify_nodes --persist
```

I risultati sono registrati nella tabella `project_health_results`; il job web
aggiorna questa tabella dopo ogni singolo controllo, insieme all'avanzamento.
Il job non crea rapporti su filesystem: il risultato visibile nel sito vive nel database.
La CI produce separatamente l'artefatto `node-verification-ci`, con regressioni
isolate che non certificano il Debian e non vengono pubblicate nel suo registro.

La presente modifica e pronta nel sorgente locale; pubblicazione e primo rilascio
sul server non vengono eseguiti dalla semplice creazione della patch.


## Uso reale e perimetro dei 30 controlli

Tutti i 30 ID del catalogo hanno ora un esecutore. Sono stati corretti i titoli e
il tipo di prova degli ID storici che finivano in `_e2e` ma non disponevano di un
vero E2E: il nome dell'ID resta compatibile con storico e collegamenti; il campo
`kind` e la descrizione dichiarano il perimetro effettivo.

- Gmail: contratti e generazione MIME con trasporto simulato, nessun account.
- Chat: grafo compilato e deleghe con agente simulato, non persistenza reale.
- Audio/Word: configurazione e trasformazioni sintetiche, non trascrizione reale.
- File: HTTP upload/download, duplicati e integrità in cartella temporanea, non NAS reale.
- Preventivi: PDF realmente generato e riletto su dati sintetici.
- Immich/Nextcloud: endpoint HTTP configurato, non upload/download reali.
- Magazzino: manager applicazioni e allowlist isolate, non import Excel esterno.
- Backup/rollback: regressioni isolate, non ripristino di un database di produzione.

I prerequisiti mancanti e i test saltati restano non verificati. Il conteggio degli
esecutori completi non significa 30 flussi reali certificati. I veri E2E esterni di
foto, Nextcloud, import Excel e restore completo richiedono ancora integrazioni e
ambienti dedicati; il pannello non li dichiara completati sulla base dei test isolati.

Una scrittura Google confermata con una lettura successiva registra `calendar_e2e`.
Una chiamata worker effettiva registra `desktop_e2e`/`laptop_e2e` soltanto per le
macchine scelte esplicitamente nell'ultima suite o nella configurazione server.
La chat nativa sul worker registra anche `worker_e2e`. Servono il modello richiesto,
il completamento e una risposta valida: l'abilitazione del worker o il clic sul test
non sono prove. Il normale utilizzo rinnova l'evidenza e la mappa la legge entro
30 secondi; cambiare modello/abilitazione o assegnazione Supervisor invalida la prova.

La chat principale segue l'assegnazione **Supervisor in Architettura**. Il test
**Macchine** usa `/generate` e non cambia quell'assegnazione. Il nuovo controllo
`worker_e2e` esegue invece `/chat` sul worker del Supervisor; se il Supervisor è
locale restituisce non verificato con l'indicazione da seguire. Le risposte remote
senza modello effettivo corrispondente o senza completamento sono rifiutate, senza
ripiego locale. Non è certificato l'uso GPU dal solo successo dell'inferenza.

I test con provider simulati disabilitano la registrazione di evidenza d'uso reale.
I dettagli pubblici non contengono testi di chat, titoli di eventi o token.
Un account di collaudo mancante non cancella una prova d'uso ancora valida: viene
conservata la sua data originale, senza prolungarne artificialmente la scadenza.

## Registro manuale del proprietario — 8 novembre 2026

Raccolta di prove di sessione, **non** esiti prodotti dalla suite `node-verification`
né attestazioni automatiche della versione del Debian (commit non raccolto
nell'interfaccia durante queste prove). Sono disponibili nei sottoelementi
della mappa mediante le osservazioni datate.

| Colore | ID puntuali | Evidenza e limite |
|---|---|---|
| Verde | `T1.p1.m1` | Chat → LangGraph → Supervisor → risposta, run 33193329 concluso; non verifica delega |
| Verde | `T8.p2.m1`, `T8.p3.m1`, `T8.p3.m2` | Assegnazione salvata, modello richiesto/riportato coincidente nei casi locale e remoto, identificativo macchina remoto disponibile |
| Verde | `R3.1.p1.m2` | Inferenze Ollama Docker 0.6B e 1.7B concluse con OK; 1.7B circa 54,46 s |
| Verde | `R1.2.p2.m2`, `R1.2.p3.m1`, `R1.2.p3.m2` | Worker 123: modello 30B riportato corrispondente, circa 30,11 s; non prova il carico della GPU |
| Verde | `installare.m2`, `assegnare.m1`, `assegnare.m2` | Worker raggiunto, assegnazione effettiva, identità modello/macchina nella traccia |
| Verde | `T10.p1.m1`, `T10.p3.m1` | Run, fasi, modello/macchina e durate registrati; non diagnosi causale automatica |
| Verde | `T6.p1.m2` | `context.selected` con budget 7040, stima 834 token, nessun turno scartato; non prova correttezza della selezione |
| Giallo | `worker.p4.m2` | Worker 123 disattivato → HTTP 502, nessun OK: fail-closed osservato. Servono errore leggibile e verifica indipendente contro fallback locale |
| Giallo | `T8.p2.m2` | Autoselezione del modello e regola worker-offline da rendere esplicite e testare |
| Giallo | `R3.2.p2.m1` | Qwen3 1.7B non rispetta 15 parole, ma capisce la revoca; potenziale limite del modello/prompt |
| Giallo | `T1.p1.m2` | Delega a specialisti non osservata nella prova route=direct |
| Giallo | `T6.p2.m1` | Contesto cronologico visto e revoca riuscita; qualità della selezione non completamente collaudata |
| Arancione | `T1` | Chat locale 1.7B con 127,89 s contro inferenza diretta con prompt diverso a 54,46 s; causa aperta, confronto non omogeneo |

Le vecchie note di «modello forse diverso», «worker non certificato» e
«router shadow/Context Manager progressivo/diagnosi causale mancanti»
non vanno più confuse con guasti confermati: le prime sono state aggiornate
con le prove raccolte; le seconde sono obiettivi futuri, non malfunzionamenti.
In particolare **upgrade GPU, CPU, RAM e NAS restano gialli**.

Il test HTTP 502 *non* attesta da solo l'assenza di un'inferenza locale
silenziosa su ogni percorso: occorrerebbe un controllo contemporaneo delle
tracce e delle risorse. Le stelle T1, T6, T8, T10 e F1 restano **parziali**.
