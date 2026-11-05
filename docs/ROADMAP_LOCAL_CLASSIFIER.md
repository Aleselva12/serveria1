# Classificatore locale degli obiettivi — prima integrazione (2026-11-05)

## Scopo e perimetro

Aggiunta alla Roadmap V2 la prima capacità **consultiva** di analisi delle priorità, eseguita **solo su richiesta**, usando Ollama già previsto da ServerIA. L'obiettivo è confrontare le schede di stelle già definite (problemi, stato dichiarato, obiettivi futuri) e formulare un elenco ragionato dei prossimi passi. Questo non è un nuovo agente autorizzato a modificare codice né un sostituto dei test reali.

**Non cambia** la struttura 515-nodi della mappa, la priorità W1/W2/W3 concordata, lo stato delle stelle, i colori di salute o il modello della chat. È un *motore separato* con interfaccia in `#homepage-schema-albero` che potrà essere collegato in seguito all'orchestratore tramite contratti e permessi specifici.

## Modello e installazione

Modello di partenza configurato: **`qwen3:1.7b`** (quantizzazione predefinita Ollama Q4_K_M, circa 1,4 GB). È un modello generalista leggero per JSON strutturato, **non Jev installato localmente**, e non è garantito che sappia ordinare correttamente i task. Verificarne la qualità sui casi reali prima di automatizzare ulteriormente.

Sul dispositivo che **ospita Ollama** e che ServerIA già raggiunge con `OLLAMA_BASE_URL`:

```sh
ollama pull qwen3:1.7b
ollama list
```

Se Ollama è dentro un container, eseguire `ollama pull` **dentro quel container**, nel volume persistente del servizio. Non eseguire un secondo Ollama sull'host senza una ragione. La pagina rileva il modello tramite `GET /api/tags`; **non avvia download o installazioni autonome**. Non abbiamo accesso SSH al Debian da questa PR: non si può dichiarare il modello già scaricato o collaudato.

Per usare un modello locale diverso senza modificare la chat, impostare:

```sh
CORA_ROADMAP_CLASSIFIER_MODEL=qwen3:0.6b
```

Il modello indicato deve già risultare in `/api/tags` del servizio configurato. Non vengono contattati provider cloud né modelli Jev/ScaleDown. Il modulo rifiuta URL Ollama pubblici: sono consentiti loopback, reti private RFC1918, indirizzi Tailscale 100.64/10 o hostname `.ts.net`, il servizio Docker locale e il gateway `host.docker.internal`.

## Funzionamento

1. Dalla Roadmap si apre **Analisi dei prossimi passi**. Il selettore contiene solo ID di stelle esistenti e propone al massimo otto elementi (W1 T1, W2 R5.2, W3 G1 e le cinque stelle-obiettivo E1/E2/F2/R1.4/T9). L'utente può sostituirli e inserire al massimo 500 caratteri di contesto aggiuntivo.
2. `GET /api/v1/roadmap/classifier/status`: prova read-only della disponibilità del modello nel catalogo Ollama, non effettua inferenza.
3. `POST /api/v1/roadmap/classifier/preview`: richiede login proprietario come gli altri endpoint ServerIA, valida ID/campi con Pydantic e formula una sola richiesta `/api/chat` locale, con `format` JSON Schema, `temperature=0`, `stream=false`, limite 1500 token generati e timeout. Un solo calcolo contemporaneo.
4. Il modello propone sei voti interi 0–5: **importanza, urgenza, dipendenze bloccanti, impatto, sforzo, rischio**. Fornisce una spiegazione e una confidenza *autodichiarata*, non calibrata. Un algoritmo deterministico combina i sei voti per l'ordinamento 0–100 (pesi 4,4,3,3,-2,-1): il modello **non** produce il punteggio totale.
5. Il backend controlla l'esatta corrispondenza degli ID e i limiti dei punteggi. Una risposta malformata, con ID inventati/duplicati o valori fuori range produce un errore, **non** una classifica fabbricata.
6. Il risultato è mostrato nel pannello, con link per aprire la relativa stella. **Nessuna scrittura**, nessuna nuova stella, nessun aggiornamento delle priorità salvate o dei risultati del registro salute. La proposta scompare al reload della pagina.

## Limiti deliberati

- Non scansiona ancora tutta la repository, i commit o il grafo delle dipendenze del codice. La prima versione usa **esclusivamente le schede dei task già note** e il contesto esplicito dell'utente. L'estrazione/categorizzazione automatica del codice necessita un processo di raccolta prove con provenienza e permessi read-only.
- Non usa automaticamente test/telemetria della Home come prova per valutare l'importanza. In futuro occorre distinguere *test corrente sul Debian*, *errore CI*, *problema dichiarato* e *ipotesi modello*, evitando di accettare indistintamente i giudizi di un LLM.
- Non diventa per ora uno strumento sempre esposto al Supervisor: la futura integrazione dovrà registrarsi nel Capability Registry come capacità **read/compute**, con attivazione e limiti espliciti, e non deve diventare proprietaria della struttura.
- Non è un sistema automatico di pianificazione: **W1/W2/W3 rimangono decisioni dell'utente**. Il pannello è una proposta separata.
- Nessun job in background e nessuna esecuzione periodica. L'inferenza su CPU può essere lenta; batch massimo otto e timeout massimo 65 secondi.
- Non inviare documenti privati o segreti in `additional_context` per prudenza, benché la richiesta resti sul servizio Ollama locale.

## Criteri per la fase successiva

Provare almeno 10 gruppi di obiettivi su Debian e desktop: correttezza JSON, latenza, coerenza con W1/W2/W3, frequenza di classificazioni non motivate, capacità di ammettere incertezza e impatto sulle risorse. Valutare `qwen3:0.6b`, `qwen3:1.7b` e, solo se utile, un modello locale più grande con lo stesso dataset. Se supera i test, introdurre una raccolta read-only delle evidenze Git/CI e infine il collegamento al Registry dell'orchestratore.

**Questa tranche non scarica il modello e non conferma il funzionamento sul Debian.**
