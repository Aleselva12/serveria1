# Roadmap V2 in ServerIA — versione pragmatica (4 novembre 2026)

## Punto di ingresso e scopo

La tessera **Schema albero** nella Home desktop e mobile apre `#homepage-schema-albero`, servita da `frontend/src/tree/TreeHome.tsx`. Non è una semplice lista di milestone: è un programma di *direzione e diagnosi* incorporato nel frontend, concepito per identificare componenti, obiettivi e problemi, e capire dove intervenire.

**Questo intervento cambia solo la pagina Roadmap**: non reimplementa la Home V2, né il backend, né l'orchestratore, né i programmi esterni. L'aspetto riprende volutamente la pagina `/v2-roadmap` del progetto Lovable *Serveria Design Studio* (colonne indice / costellazione / inspector, sfondo scuro, stelle colorate, pannello temporale), ma usa SVG navigabile esistente invece di importare subito Three.js, TanStack Router e il design system indipendente di Lovable.

## Fonte dati e classificazione

- Fonte: `qwe`, branch `progetti/cora-serveria`, `cora-plan.json`, revisione `CORA-V2-2026-11-03`.
- Copia statica in repo: `frontend/src/tree/cora-plan.snapshot.json`: **515 nodi**, **45 stelle** (14 radici, 13 tronco, 18 rami), 151 pianeti, 304 lune, 37 relazioni concettuali.
- Le sei aree radici: R1 Macchine, R2 Dati, R3 Modelli IA, R4 Ambiente operativo, R5 Affidabilità, R6 Sicurezza; R6.2 Permission Engine resta nelle radici.
- T1–T13: tredici stelle del tronco a **disposizione libera**, senza falsa catena seriale o dipendenze verso Memoria/Context Manager non approvate.
- Sette rami A–G: A Conversazione, B File, C Comunicazioni, D Programmi autonomi, E Clienti, F Distribuzione, G solo Programmatore.
- Le posizioni grafiche e i collegamenti visivi del tronco (in `Constellation.tsx`) sono un progetto di presentazione, **non attestano dipendenze runtime**. Le 37 relazioni dichiarate sono mostrate solo quando selezioni una stella.
- In panoramica si mostrano solo aree e stelle; pianeti e lune si espandono nell'inspector della stella. ID preservati (es. `worker`, `installare`, `assegnare`, `immich`, `C1a`–`C1e`).

## Stato, salute e provenienza

La UI separa **realizzazione** (`present`, `partial`, `planned`, `idea`) e **attenzione derivata** (`unknown`, `plan`, `minor`, `problem`, `ok`).

- **Grigio**: da valutare / placeholder / nessuna prova.
- **Giallo**: obiettivi futuri documentati, ma nessun guasto dimostrato.
- **Arancione**: problemi o dubbi documentati nella stella, non automaticamente guasti di produzione.
- **Rosso**: test collegato che ha effettivamente restituito `fail`, non scaduto per i test automatici.
- **Verde**: soltanto se il set di verifiche collegato è superato e comprende un vero E2E recente con ambiente e commit identificabili. Un preflight OK non basta.

Questa è una **prima policy visuale locale**, da discutere; non scrive alcuna priorità dentro il modello, non altera il catalogo né attribuisce esiti inventati. Se il backend è non raggiungibile, i test sono sconosciuti; non automaticamente rossi.

`TreeHome` chiama solamente l'API **esistente** `api.healthDashboard()` ogni 30 secondi; non crea nuovi check runner né database. L'associazione nodo→controlli è in `frontend/src/tree/model.ts:checks`, dove alcuni ID rappresentano verifiche future già elencate nel catalogo e possono non avere esiti. Vengono mostrati data, commit, ambiente e tipo di test. `atlas-evidence.json` è etichettato come prova locale di Atlas, non come certificazione del Debian.

Conserva in scheda le quattro viste **Presente, Problemi, Futuro, Storia**. Le osservazioni dell'utente sono esplicitamente attribuite, i problemi sono elencati da `knownIssues[]`, gli obiettivi da `timeline.future[]` e `roadmapRefs[]`. Il passato vuoto resta vuoto finché non sarà collegato a commit/decisioni veri; una `earlierNote` è una nota precedente, non un commit datato.

La prossima sequenza W1 collaudo orchestratore → W2 aggiornamenti Immich/Nextcloud → W3 Programmatore resta accessibile sotto la mappa. M3 E1 CRM e M4 E2/F2 sono già nel loro ramo, non in un ulteriore ramo «futuro».

## Come valutare il risultato

1. Aprire `#home` e cliccare **Schema albero** (desktop e telefono); verificare che si apra `#homepage-schema-albero`, senza aprire una seconda app o un backend separato.
2. Controllare che il tronco mostri **13 stelle parallele** con alcune linee sensate, non 13 elementi uno sotto l'altro.
3. Selezionare **C1**: aprire i pianeti `C1a` interpretazione, `C1b` evento unico, `C1c` notifica e le idee `C1d` e `C1e`. Le lune si vedono solo espandendo il pianeta.
4. Selezionare **F1**: il worker è una stella; `installare` e `assegnare` sono pianeti distinti. **F2** è un'altra stella, per agenti operativi remoti con permessi.
5. Selezionare **T1**: vedere problemi, lavori futuri e controlli correlati alla chat. Nessun test automatico deve trasformare «presente» in «funzionante» senza prova applicabile.
6. Selezionare **E1** e **F2**: gli obiettivi cliente SQL e distribuzione agenti figurano fra i futuri, non già realizzati.
7. Usare ricerca, filtri, vista elenco, zoom, pan e pulsante esportazione. Verificare ambiente desktop/mobile.
8. Eseguire `cd frontend && npm test && npm run build`, e controllare i workflow di CI del commit.

## Parti deliberatamente lasciate a una tranche separata

- **Grafica 3D: esclusa per decisione del proprietario (4 novembre 2026).** La Roadmap deve restare bidimensionale, migliorando libertà di navigazione, zoom, pan e leggibilità; non riaprire autonomamente il progetto Three.js.
- **Modifica strutturale da agenti/IA: non prevista.** Solo il proprietario, tramite decisioni esplicite e lavoro sulla repository, modifica rami, stelle, pianeti, lune, collegamenti e architettura. Non aggiungere un editor IA automatico o localStorage come secondo database della pianta.
- **Associazione automatica di tutti i file/funzioni/commit alle stelle:** per ora esiste un primo registro *esplicito e verificato* in `frontend/src/tree/codeLinks.ts`, con accesso al codice e alle pagine reali di ServerIA. L'estensione automatica completa e la verifica del cambiamento dei riferimenti restano future; non accettare proposte non confermate come mappature certe.
- **Storico temporale completo e riconciliazione dei commit**: progettare provenance, versione, sostituzioni e stato precedente senza inventare il passato.
- **Propagazione intelligente dei guasti e analisi causale per dipendenze**: la diagnosi attuale legge soltanto esiti di test già registrati e problemi dichiarati. Il tracing reale dei run resta nel lavoro orchestratore W1.
- **Nuovi test E2E isolati e deploy di servizi**: appartengono al registro salute e ai relativi servizi, non alla pagina Roadmap. Nessun update né scrittura su file o database di produzione da questa interfaccia.

Non realizzare automaticamente una versione Three.js: **la scelta corrente è 2D**. Conservare la pianta canonica, gli ID, l'inspector e l'accesso al catalogo salute in ogni successiva revisione grafica.

## Revisione V2.1 — decisioni 4 novembre 2026

### Navigazione grafica 2D
La Roadmap usa due livelli spaziali distinti, senza introdurre un motore 3D:
- Panoramica delle 45 stelle e delle aree di radici/tronco/rami, con tronco libero;
- **Selezione di una stella → scena isolata** con solo la stella scelta, tutti i suoi pianeti e le loro lune. «Tutta la mappa» torna alla panoramica. Rotella/mouse, trascinamento, zoom e gesti touch si applicano a entrambe le scene. I pianeti/lune rimangono anche consultabili nell'inspector.
- Segnale grafico della stella obiettivo non implementata: centro grigio/vuoto, anello tratteggiato e dicitura «◇ OBIETTIVO». Fascia di accesso rapido alle stelle-obiettivo in Home Roadmap, senza ramo “futuro”.
- Colori applicati **direttamente alla stella SVG**, non soltanto alle voci in elenco.

### Governance: solo test di stato, mai modifica strutturale automatica
- La gerarchia architetturale, gli ID, i link e i significati appartengono al proprietario. Un agente o modello non può introdurre, spostare o eliminare stelle, rami, pianeti o lune in modo autonomo.
- I test del catalogo già esistente possono cambiare **soltanto la proiezione dello stato osservato** di un nodo a schermo; per esempio un E2E passato e attribuito a un pianeta può risultare «prova funzionale disponibile», e un test fallito può renderlo rosso.
- La snapshot JSON di `qwe` resta la base delle decisioni umane: i risultati di test non cambiano permanentemente `status`, `priority` o struttura del JSON. Un eventuale “presente” automatico resta attribuito a test/ambiente/commit, non è promozione architetturale, finché non lo confermiamo.
- L'unico registro dei test è quello nel backend; la pagina recupera `api.healthDashboard()` senza attivare un altro runner.

### Collegamenti al codice esistente
`frontend/src/tree/codeLinks.ts` contiene una prima mappatura verificata fra stelle e file reali di ServerIA (`main`) e Atlas/qwe (`progetti/cora-serveria`), oltre ai link verso pagine native di ServerIA. Sono citazioni di sorgenti, non claim che il codice sia funzionante, né analisi semantiche autonome. Le relazioni fra stelle rimangono nel JSON canonico.

### Lavoro differito: diagnosi causale avanzata
**Da aggiungere nella futura evoluzione T10–T11 dell'orchestratore.** È necessario attribuire automaticamente un errore all'hop specifico (chat → supervisor → capability → agente → modello/worker → risposta), stabilire se una modifica di un altro componente ha provocato una regressione e raccogliere evidenze su commit/ambiente. La Roadmap V2.1 NON inventa questo livello diagnostico: per ora mostra solo prove esplicite, problemi documentati e collegamenti noti.
