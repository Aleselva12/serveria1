# Collaudo e revisione memoria — 19 novembre 2026

Base esaminata: `52621159f66740f99447d9632fcbafbd90532714`.
Ambiente: checkout isolato, Python 3.12, dipendenze di requirements-dev.lock,
frontend installato con npm ci. Nessun accesso ai dati privati del Debian.

## Esito e limiti

Le suite isolate verificano contesto proprietario, revisioni obsolete, fonti,
classificazioni, query di ricerca, fallback senza embedding, episodi e stato
temporaneo. Database e provider sono simulati in questi test: il loro successo
non certifica persistenza PostgreSQL o qualità semantica di Ollama.

Collaudo backend finale mirato: 69 test, 55 superati e 14 saltati per assenza
locale di PostgreSQL sacrificabile (10 preesistenti e 4 nuovi SQL). Nessun errore.
Cinque controlli eseguiti dal runner una tantum: tutti pass, 24 test isolati
complessivi senza skip. Suite frontend completa: 269 test superati, nessuno saltato.
La build TypeScript/Vite viene verificata prima della pubblicazione della PR.

È stato tentato l'avvio di PostgreSQL+pgvector temporaneo tramite pgserver
(strumento del solo ambiente di collaudo, nessuna dipendenza del progetto aggiunta).
L'ambiente vieta la creazione di socket: integrazione SQL non eseguita localmente.
I test SQL richiedono esplicitamente un database sacrificabile; la CI esistente
fornisce PostgreSQL+pgvector e le due variabili CORA_DATABASE_URL e
CORA_RUNTIME_TEST_DATABASE_URL. Un test saltato non è un successo SQL.

## Risultati dell'esame del codice

| Ambito | Presente | Limite |
| --- | --- | --- |
| Proprietario | Un testo globale, revisioni e caricamento selettivo | Non è una biblioteca di schede |
| Persistente | Tipi, fonti, revisioni, classificazione, scadenza, ricerca ibrida | Non ha grafo navigabile né isolamento strutturale per progetto |
| Episodi | Creazione, lista, conversazione/agente e metadati | Nessun chiamante automatico di create_episode nel runtime esaminato; nessun legame strutturale al run |
| Working memory | API, upsert per agente/conversazione, TTL e pulizia alla lista | Non prova alimentazione autonoma o ripresa di piani |
| Cronologia | Messaggi originali e sintesi incrementali | Una sintesi non è una memoria persistente o un registro completo del server |
| Evidenze operative | Operation journal e domain events persistenti | Non sono ancora un registro letterale unificato della memoria |

## Controlli disponibili nella roadmap

Quattro nuovi ID sintetici, eseguiti dal runner esistente con ambiente ripulito:
memory_owner_regression, memory_semantic_regression, memory_episodes_regression,
memory_working_regression. Ogni controllo dichiara i limiti della propria prova.
Gli stessi ID sono collegati ai pianeti/lune coperti, senza nuovi runner UI.

memory_e2e rimane la prova esistente di scrittura/rilettura da processi distinti:
copre una nota sintetica, non episodi, TTL, embeddings, riavvio del servizio o
comprensione delle risposte. È collegato al recupero persistente, non a tutti
i livelli della memoria.

Nuove prove SQL sacrificabili: ricerca lessicale e scadenza/cancellazione a cascata;
distanza pgvector con vettori controllati e filtro modello; stato temporaneo con
isolamento agente e scadenza; roundtrip episodio con fonte e conversazione.
Restano anche le prove preesistenti su revisioni, approval e sintesi incrementali.

I risultati locali/CI non vengono inseriti come manual_pass e non colorano il
Debian di verde. Dopo installazione, gli stessi controlli potranno produrre esiti
attribuiti alla release reale. L'assenza di prova sul server resta dichiarata.

## Decisioni strutturali

La struttura nuova è descritta in [MEMORY_DESIGN.md](MEMORY_DESIGN.md).
Gli ID storici restano; aggiunti cinque pianeti e dodici lune future sotto T7.
Gli archivi implementati hanno stato declared present dove il contratto ristretto
esiste; integrazioni incomplete restano partial, obiettivi futuri planned/idea.
Il Custode resta futuro; le revisioni già presenti sono descritte nei nodi attuali.
Il funzionamento e i dati della memoria non sono modificati da questa tranche.
