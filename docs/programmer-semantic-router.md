# Router semantico del programmatore

Questa implementazione parte da main `34897bc`. Sostituisce nel percorso runtime
la selezione lessicale con una classificazione semantica quando il Context Manager
è attivo. Il precedente branch `feature/programmer-simple-context` non è una
prerequisito e non va unito: contiene anche una coda duplicata sintatticamente errata.

## Comportamento

- Una chiamata locale allo stesso modello selezionato per il programmatore, nel
  nodo prepare; nessuna riclassificazione nelle successive iterazioni dei tool.
  Non è una nuova rete addestrata o un piccolo modello dedicato.
- Output JSON validato: intent, context, tool_groups, difficulty 0–10, confidence.
  Il punteggio non governa da solo risorse o autorizzazioni. La confidence è una
  stima del modello, non una probabilità calibrata; soglia conservativa 0.85.
- Classifica gli ultimi 6 messaggi, con indicazione di storia precedente omessa.
  Massimo 6000 caratteri complessivi; input più grandi, multimodali o contenenti
  scambi tool recenti tornano al catalogo completo senza un'inferenza aggiuntiva.
- Conversazioni/spiegazioni autonome, di qualsiasi argomento, espongono il solo
  catalogo. Il catalogo è una via di recupero, quindi NON è un percorso zero-tool.
  Dopo la sua chiamata o un errore tool sono disponibili tutti i tool nel turno.
- Ricerca/modifica mantiene gli strumenti essenziali e aggiunge le famiglie utili.
  Nomi di tool espliciti e tool già chiamati restano disponibili.
- Solo per un singolo messaggio autonomo si omettono dal prompt i metadati estesi
  del workspace e l'elenco delle skill. Restano identità, politiche, contesto
  permanente e workspace ID necessario al catalogo. Il prompt completo ritorna
  dopo il recupero del catalogo. Tutti i messaggi originali passano a fit_messages:
  nessun nuovo taglio della cronologia o degli scambi tool.
- I campi history/memory/files impediscono la riduzione al percorso conversazionale.
  Non introducono nuovi strumenti di ricerca memoria né caricamenti automatici:
  restano il contesto disponibile e i recuperi governati esistenti.
- Errore del provider, JSON invalido, classificazione incerta o router disattivato:
  prompt completo e tutti i tool. Cancellazione e scadenza del run si propagano.
- Il selettore lessicale precedente rimane nell'API locale select_tools/prepare
  per compatibilità, ma il grafo passa sempre una decisione esplicita e non lo usa.

## Attivazione e ritorno al percorso precedente

In deploy.env dell'API, quindi ricreare l'API con la procedura abituale:

```dotenv
CORA_CONTEXT_MANAGER_ENABLED=true
CORA_CONTEXT_ROUTER_MODE=semantic
CORA_CONTEXT_ROUTER_TIMEOUT_SECONDS=5
```

Default del Context Manager ancora false: l'aggiornamento non lo attiva da solo.
CORA_CONTEXT_MANAGER_ENABLED=false ripristina il prompt e catalogo originali.
CORA_CONTEXT_ROUTER_MODE=off mantiene il manager ma usa il fallback completo.
Non ci sono download modelli, nuove dipendenze, cambi modello o chiamate cloud.

La richiesta di classificazione usa stream=false, massimo 256 token in uscita,
timeout di trasporto configurabile tra 0.5 e 15 secondi. Non è una garanzia di tempo
massimo dell'intero run o di immediato arresto dell'inferenza sul server Ollama.
Thinking disattivato dove supportato; GPT-OSS richiede un livello e usa low.
Se il modello/provider non supporta schema o thinking, il fallback resta operativo.

## Misure e limiti

Evento programmer.context_route e run.timings.programmer_context: decisione,
status, durata, tipo errore e usage Ollama quando presente; non prompt o contenuti.
Le tracce modello distinguono cora_role=programmer_router dal programmatore.
La classificazione costa una chiamata supplementare e può invalidare la cache del
prompt del modello: meno token nella risposta non garantisce minore tempo totale.
Non sono ancora misurate accuratezza semantica e latenza su Ollama reale.

Verifiche offline:

```sh
python -m unittest discover -s tests -p 'test_programmer*.py'
python tests/programmer_context_benchmark.py
```

Il benchmark offline ora simula anche la classificazione, così non contatta Ollama.
Conserva lettura/scrittura/verifica reali nel workspace temporaneo: per la modifica
valida e quella con sintassi errata, gli esiti A/B restano equivalenti; 21 → 12 tool,
5571 → 3993 token stimati al primo passaggio. Non include token o latenza reali del
router e non dimostra un guadagno complessivo.

Smoke test sul server, senza eseguire tool o modificare workspace:

```sh
python tests/programmer_router_benchmark.py --live
```

Riporta otto casi IT/EN, dipendenza dalla storia, file, rilascio e spiegazioni;
controlla le aspettative principali, mostra fallback, tempi, classificazioni e
stime degli schemi selezionati. Eseguire dopo il riscaldamento e ripetere almeno
3 volte. Il test usa il router anche se il manager non è attivato, ma rispetta
CORA_CONTEXT_ROUTER_MODE. Non è un benchmark end-to-end della risposta.
Prima di considerare riuscita l'ottimizzazione confrontare anche il run completo
con manager false/true, stesso modello e richiesta: durata totale, accuratezza,
recuperi del catalogo, errori e check finali. La scelta automatica del modello resta
fuori da questa prima fase.
