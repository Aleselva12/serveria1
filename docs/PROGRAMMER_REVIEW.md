# Revisione del Programmatore

Data: 11 ottobre 2026. Prima lettura della struttura e del flusso, confrontata
con origin/main. Nessuna modifica al comportamento applicativo in questa revisione.

## Grafica condivisa

- Figma Design: proposta per progettare insieme con componenti riutilizzabili;
  il progetto grafico va poi implementato nel frontend React esistente.
- Plasmic: alternativa per comporre visualmente componenti React e sincronizzarli
  nella repository tramite codegen. Richiede una prima integrazione e una verifica
  della gestione dei file generati.
- Penpot: alternativa aperta, con ispezione CSS/HTML/SVG. Accesso diretto da questa
  sessione non verificato.
- Da scegliere con Alessandro lo strumento prima di costruire la nuova pagina.

## Struttura fisica

`programmer_agent/` contiene 22 file, di cui 11 moduli Python al primo livello
(incluso `__init__.py`), 5 skill, 3 template, 2 Dockerfile e un README.

- `api.py`: richieste HTTP, avvio delle esecuzioni, salvataggio della conversazione.
- `programmer_graph.py`: ciclo LangGraph fra modello e strumenti.
- `programmer_tools.py`: 21 strumenti esposti al modello.
- `workspace.py`: copie separate, percorsi, lettura/scrittura e differenze.
- `checks.py`, `contract_checks.py`: controlli e verifiche dei contratti.
- `knowledge.py`, `build_graph.py`: skill/template e mappa Graphify del codice.
- `components.py`: registrazione e pacchetti dei componenti creati.
- `releases.py`: collegamento al servizio aggiornamenti per i rilasci.

La pagina usa `frontend/src/components/Programmer.tsx`, `WorkspaceEditor.tsx`,
`ProgrammerArtifacts.tsx`, `ProgrammerReleases.tsx` e il servizio
`frontend/src/services/programmerApi.ts`. Trasporto eventi condiviso:
`frontend/src/services/runtimeApi.ts`; grafica: `frontend/src/style.css`.

Dipendenze condivise principali: `core/runtime.py` (coda e stato),
`core/models.py` (modello e limiti), `core/context_budget.py` (contesto),
`core/chat_store.py` (conversazione), `core/execution_traces.py` (diagnostica),
`core/governance.py` e `core/permissions.py` (regole degli strumenti).

Il servizio host in `updater/` è separato: il modello non esegue liberamente
comandi sul server. Il workspace host è sotto
`/srv/cora-server-test/state/programmer`, visto dall'API come `/state/programmer`.

## Percorso della richiesta

1. Il frontend invia workspace e messaggio a `/api/v1/programmer/runs`.
2. L'API accetta il lavoro; il runtime assegna un ID e lo mette in coda.
3. `execute_programmer` salva il messaggio e prepara il contesto.
4. Il grafo prepara le istruzioni e invoca il modello con gli strumenti.
5. Se il modello chiede uno strumento, lo esegue e torna al modello.
6. Se non chiede strumenti, termina; l'API salva la risposta.
7. Il frontend riceve testo e stato tramite eventi SSE.

Il grafo LangGraph controlla l'esecuzione. La mappa Graphify descrive i file:
sono due oggetti diversi, e Graphify non è necessario per inviare una chat.

## Riscontri e lavori da fare

- [x] Mappati file, responsabilità e percorso della richiesta.
- [x] Individuato layout potenzialmente errato della chat: `.copilot-body`
  usa flex senza `flex-direction: column`, con messaggi come figli diretti.
- [ ] Correggere e verificare il layout su desktop e telefono nel lavoro grafico.
- [ ] Concordare una struttura più leggibile: conversazione, codice/diff,
  verifiche/rilasci distinti, con le operazioni avanzate meno esposte.
- [x] Recuperare stato, metriche e fasi dell'esecuzione `kind=programmer`
  `0f6b614b-dde1-4bab-85fd-795601558e6e`: completed, senza errori.
- [x] Misurare una chiamata al modello nel percorso Cora: tutte le 21 definizioni degli
  strumenti sono associate a ogni chiamata, insieme al contesto e alle istruzioni.
  Il benchmark Ollama diretto non misura questo carico.
- [ ] Valutare un limite ai tentativi ripetuti: gli errori degli strumenti tornano
  al modello; il grafo ha un limite di ricorsione pari a 60, non una specifica
  regola contro la ripetizione dello stesso errore.
- [ ] Valutare la serializzazione: se arrivano più tool call nella stessa risposta,
  il codice conserva solo la prima. Le altre non vengono accodate.
- [ ] Distinguere fine dell'esecuzione e risultato del lavoro: il grafo termina
  senza tool call; non impone un controllo finale su file e test. Il prompt richiede
  onestà, ma questo non costituisce una verifica automatica del risultato.
- [ ] Verificare separatamente coda, chiamata al modello e stream frontend.
  Il runtime ha uno slot globale condiviso anche dai controlli.

## Riscontro server del 12 ottobre 2026

L'utente ha fornito la diagnostica persistente del run sopra indicato, iniziato
l'11 ottobre alle 23:34:52 UTC. Durata totale 218,378 s; coda 0,171 s;
una chiamata modello 217,746 s (99,71% del totale). Preparazione del nodo 1,42 ms.
Il campione non contiene chiamate a strumenti; diagnostic_truncated=false.

Ollama riporta 2551 token di input, 101 token generati, caricamento 7,953 s,
elaborazione input 136,568 s e generazione 73,135 s. Il primo token registrato
dal callback del modello arriva dopo 186,120 s. Non coincide necessariamente
con il primo token interno di ragionamento o con il primo testo visibile nel browser.
La metrica node_ms somma span annidati e non rappresenta tempo aggiuntivo.

Questa esecuzione dimostra che il backend ha terminato; localizza l'attesa nella
chiamata al modello. Non dimostra qualità della risposta, capacità di modificare
codice né consegna della risposta al browser. Restano da isolare peso degli schemi
degli strumenti, contesto permanente/storico, ragionamento ed eventuale contesa
di CPU/RAM. La configurazione riportata è CPU only, 2 core fisici, 15,36 GiB RAM;
non è una misura dell'utilizzo delle risorse durante il run.

- [ ] Confrontare richieste a parità di modello e carico, separando istruzioni,
  cronologia e definizioni degli strumenti.
- [ ] Verificare la risposta salvata e la ricezione finale nella pagina.
- [ ] Eseguire poi una richiesta minima di modifica con verifica di file e test.

Non sono state applicate correzioni al server da questa revisione. Restano valide
le verifiche e le attività aperte in SERVER_VALIDATION.md.
