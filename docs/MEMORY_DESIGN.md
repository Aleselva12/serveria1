# Memoria Cora — decisioni del 19 novembre 2026

Le decisioni di progetto derivano dalla conversazione con il proprietario del
19/11/2026. La sezione **Base operativa per ServerIa2** descrive ciò che è
disponibile oggi.

## Biblioteca e rappresentazioni

Il registro letterale conserva evidenze originali: messaggi, richieste, risultati,
errori e conferme osservate. Una richiesta di azione non prova l'esito. Correzioni
e verifiche sono annotazioni successive. Chat, operation journal e domain events
esistono già, ma non costituiscono una biblioteca letterale unificata completa.
Contenuti sensibili, retention e confini di raccolta devono essere definiti prima
di estendere la registrazione; non è previsto copiare indiscriminatamente tutti
i dati del server.

`GET /memory/evidence/runs/{run_id}` restituisce i messaggi utente e assistente
attribuiti all'esecuzione e una pagina di eventi del suo run radice. Per scorrere
gli eventi, usa `next_cursor` come parametro `after`. La risposta riusa gli
archivi esistenti e i messaggi storici privi di ID di esecuzione non sono attribuiti
per inferenza.

Il registro rielaborato contiene resoconti leggibili, derivati e rigenerabili,
con riferimenti agli originali. Arriva dopo la base letterale. Gli episodi e le
sintesi chat attuali sono le basi per questo lavoro.

La memoria simbolica rappresenta entità, fatti, decisioni e relazioni tipizzate.
Ogni affermazione distingue dichiarazione, osservazione e deduzione; conserva
fonte, versione, ambito e validità temporale. Un documento e un grafo sono due
viste complementari, non fonti concorrenti.

La biblioteca presenta schede con titolo, descrizione breve, contenuto, fonti,
versioni e collegamenti. L'indice gerarchico dà un ingresso e le relazioni
consentono percorsi trasversali senza duplicare persone o progetti. PostgreSQL
resta autorevole; Markdown è vista/esportazione, non una seconda copia modificabile
indipendentemente. Ambiti: globale, azienda, progetto e attività.

## Navigazione e memorie brevi

Il Context Manager T6 dovrà permettere indice, ricerca, apertura scheda,
attraversamento dei collegamenti e lettura della fonte originale, con budget,
permessi, provenienza e informazioni mancanti espliciti. Le attuali context
pages, la selezione lessicale e il budget non realizzano già questo percorso.

Un piccolo nucleo di memorie brevi curate orienta le attività. Candidati iniziali per la revisione:

- uso prevalentemente remoto tramite Tailscale;
- obiettivi concreti, verificabili e utili al lavoro quotidiano;
- fatti verificati distinti da ipotesi e incertezze;
- implementazione separata dal collaudo finale;
- elaborazione riepiloghi Mail nella finestra 03:00–04:00 Europe/Rome.

Solo poche indicazioni universali restano sempre disponibili; le altre vengono
recuperate per ambito. Una memoria recuperata non concede permessi e il testo di
un documento non diventa automaticamente un'istruzione autorevole.

La "forza gravitazionale" è una sperimentazione successiva: pertinenza,
importanza e collegamenti possono influenzare l'ordinamento, mai dimostrare verità
o prevalere su una correzione esplicita. Formula, decadimento e criteri non sono
ancora approvati come comportamento operativo.

## Roadmap e criteri di chiusura

T7.p1–p4 descrivono i quattro archivi esistenti. T7.p5 comprende la revisione manuale e il futuro Custode autonomo.
T7.p6–p10 descrivono registro letterale, rielaborato, simbolico, biblioteca e
memorie brevi. T6 governa il recupero, senza duplicare questi archivi.

La prima implementazione dovrà dimostrare, su dati sintetici, il ciclo
salva → nuova conversazione/processo → ritrova → correggi → rileggi; isolamento
degli ambiti; navigazione fino alla fonte; gestione di conflitti e budget.
Un test dei contratti non certifica pertinenza semantica o inferenza reale.

## Base operativa per ServerIa2

In **Gestione Memoria → Biblioteca e registro delle esecuzioni**, apri un run
recente o cercalo per ID. Il resoconto mostra lo stato e i tempi registrati,
l'episodio associato quando è disponibile e gli originali consultabili. Gli
eventi appartengono al run radice e sono paginati. I messaggi e l'episodio
appartengono al run selezionato. I nuovi episodi della chat salvano il riferimento
al run. Gli episodi precedenti restano consultabili dalla memoria episodica.

Crea una bozza dalla fonte o apri un ambito come `serveria/serveria2` e cerca per
titolo, descrizione o contenuto. Gli ambiti usano fino a tre livelli
`azienda/progetto/attività` e l'ambito `global` è separato. Il filtro corrisponde
all'ambito esatto. I collegamenti possono puntare a schede dello stesso ambito o
di un ambito superiore. È un criterio di navigazione per il proprietario
autenticato. Una futura integrazione multiutente richiederà regole di accesso
per ambito anche sulle fonti.

Il proprietario può revisionare, approvare o archiviare una scheda. Le versioni
precedenti rimangono leggibili. Le osservazioni e le deduzioni approvate
richiedono una fonte. Le relazioni tipizzate consentono di registrare
contraddizioni e sostituzioni. L'eventuale risoluzione è un atto editoriale.
Memorie brevi e decisioni curate sono schede della stessa biblioteca, quindi
condividono revisione, fonti e selezione per ambito. La memoria semantica esistente
continua a fornire le proprie ricerche. La biblioteca è consultata ed esportata
su richiesta e non viene inserita automaticamente nel prompt.

Il pulsante **Esporta schede approvate** produce un JSON per ambito con le
versioni correnti, valide, le relazioni e i riferimenti alle esecuzioni. È un
pacchetto di consultazione, utile come contesto di progetto per ServerIa2.
Gli identificativi delle fonti rimandano al ServerIa originario. Il pacchetto
non trasporta cronologia delle revisioni o dati originali dei run.
**Importa bozze** accetta il formato `serveria-memory-drafts-v1`: un campo
`format` e un array `cards` di richieste di creazione bozza. L'operazione è
atomica; chiavi già presenti bloccano il pacchetto, preservando le schede
correnti. Gli export di consultazione usano il formato
`serveria-memory-library-v1`.

### Prove e stato della mappa

- `memory_e2e` scrive, rilegge da un altro processo e pulisce una nota sintetica.
- `memory_library_e2e` crea e corregge schede in un ambito sintetico, verifica la
  revisione obsoleta, rilegge ricerca, collegamenti, isolamento ed export da un
  altro processo, poi pulisce le fixture.
- `memory_evidence_regression` verifica l'attribuzione e il resoconto su archivi
  simulati. I test PostgreSQL dedicati provano anche importazione atomica,
  scadenze, navigazione delle fonti e proiezione di episodi e messaggi.

Gli esiti locali non cambiano i colori della release Debian attiva. Restano da
integrare il diario periodico, il Custode autonomo, la riconciliazione assistita
delle contraddizioni, il recupero della biblioteca da parte di T6 e le politiche
di retention delle evidenze. I pesi gravitazionali restano un'idea.
