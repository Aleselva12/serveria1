# Home: obiettivi e stato osservato — 25 ottobre 2026

## Quadro corrente

La Home desktop e mobile usano lo stesso componente `ProjectRoadmap` e gli stessi 19 obiettivi in quattro macroclassi:

- M1: decisioni di architettura hardware/software ancora aperte;
- M2: implementazioni presenti da collaudare nella configurazione reale;
- M3: servizi, applicazioni ed estensioni da completare;
- M4: automazioni ancora da progettare/implementare.

La fonte attuale è `docs/project-status.json`. Dopo una modifica eseguire `python deploy/render_roadmap.py`: aggiorna `frontend/src/project-status.generated.json`, incluso anche nelle build Docker del solo frontend. I test controllano che sorgente e copia siano identici, che i gruppi siano validi e che gli obiettivi non siano duplicati.

`docs/roadmap.json`, `17 passi.txt` e la loro copia frontend conservano le 17 decisioni storiche del 18 ottobre: non vengono più mostrati come elenco corrente. La chiusura dell’episodio PostgreSQL e l’esclusione del monitor semantico restano conservate nello storico. Programmatore e nuove capacità di sincronizzazione/gestione file mantengono il rinvio hardware. Non si dichiara completata un’attività sulla sola presenza di codice o pulsanti.


## Estensione M1/M2 — roadmap con controlli periodici (branch di sviluppo)

### M1: architettura desiderata, distinta dall'installazione attuale

La pagina ora mostra quattro nodi: **Debian** (API Cora e applicazioni correnti)
e **desktop RX 6800** (risorsa GPU), entrambi presenti; **laptop worker**
aggiuntivo e **NAS dedicato** sono previsti, non installati né collaudati.
Un nodo presente non implica inferenza GPU realmente provata. I nuovi traguardi
aperti riguardano orchestrazione delle attività sui nodi, confronto con sistemi
operativi/piattaforme AI e strategia dei modelli (Colibrì è un candidato da
valutare, non un modello installato).

### M2: due assi indipendenti

- **Sviluppo**: dichiarazione di repository («In costruzione», ecc.), con
  funzioni mancanti e problemi già noti. Non significa che il prodotto sia rotto.
- **Funzionamento**: rimane **Da verificare** finché non esiste un collaudo
  funzionale del flusso completo, datato e riferito alla versione installata.
- **Ambiente / prerequisiti**: `core/project_checks.py` esegue ogni 300 secondi,
  nel processo API, esclusivamente quattro prove non distruttive: SELECT 1 su
  PostgreSQL SENZA migrazioni, lettura della cartella IA, disponibilità dichiarata
  del motore Audio e lettura del catalogo Ollama. Lo stato «Presente» significa
  soltanto che il prerequisito ha risposto, NON che il programma funziona.

La pagina legge `GET /api/v1/project/checks` ogni 30 secondi quando aperta.
I risultati vengono scartati dalla UI se più vecchi di due intervalli; lo
snapshot è conservato **solo in memoria del processo**, quindi sparisce al
riavvio. In un'installazione con più processi API ogni processo mantiene il
proprio snapshot; non è un registro storico unico né un coordinatore condiviso.
La raccolta non genera email, eventi, file, inferenze, restore o modifiche.
Gli errori non restituiscono credenziali o dettagli di connessione.

Sono visibili, separatamente per ogni obiettivo M2, le verifiche end-to-end
ancora necessarie e le mancanze note. Al momento questi campi sono revisionati
dalla repository e non vengono compilati automaticamente da un agente.

**Passi successivi aperti:** realizzare test funzionali sintetici isolati,
registrazione duratura delle prove (data, versione, ambiente, esito), un
meccanismo di schedulazione condiviso in caso di più processi API e un percorso
di validazione esplicita prima di dichiarare «funziona». I test unitari e la
verifica HTTP non equivalgono al collaudo operativo del Debian.

## Correzioni del resto della Home

- Eliminati “cinque priorità” su un elenco di 17 passi, ripetizioni dello stesso backlog e il badge positivo “Riscontrato” applicato a un collaudo ancora da svolgere.
- Raggruppamento apribile da tastiera e adattato allo schermo mobile; riepilogo dinamico di obiettivi e macroclassi.
- Servizi descritti come raggiungibili/non raggiungibili/non verificati. Un controllo HTTP non certifica un flusso end-to-end; nessuna certificazione di operatività aggiunta.
- Sul telefono, assenza di health non trasforma Ollama in “Offline”; i servizi restituiti non vengono duplicati dalle righe di fallback. Le misure assenti restano trattini.
- Aggiorna stato ricarica sia health sia monitoraggio; errori di telemetria e servizi restano indipendenti e le richieste non si sovrappongono sullo stesso canale.
- Unità disco GiB coerenti con la divisione per 1024³; testi generici per dispositivo e nessun nome personale fisso nel saluto desktop.

Le misurazioni sono quelle visibili al processo Cora, eventualmente dentro un container. Il controllo Ollama riguarda il provider locale configurato, non la prova di inferenza dei singoli agenti assegnati al worker.

## Prove e limiti

La revisione si basa su main `a8fb19d6acfdec39c65c6c710e4f7769f9c3db3b` e sul confronto README/codice precedente. Le repository esterne del magazzino/preventivi e l’installazione Debian attiva non sono state ispezionate nuovamente: gli obiettivi ne richiedono la verifica, senza inventarne lo stato.

Verifiche frontend e sincronizzazione dati eseguite sul checkout locale; anteprima browser offline desktop e 390×844. Nessun backend, database, OAuth, modello o servizio reale avviato. La navigazione offline verifica contenuti e disposizione, non i servizi. Nessun merge o deploy.


Risultati: 130 test frontend superati (5 regressioni nuove sulla Home), build TypeScript/Vite riuscita; 3 test backend mirati superati, inclusa la sincronizzazione delle fonti. `git diff --check` superato. Resta il warning preesistente sul bundle oltre 500 kB. Browser offline: nessun overflow orizzontale nei viewport mobile e desktop osservati. CI GitHub della PR da verificare separatamente.
