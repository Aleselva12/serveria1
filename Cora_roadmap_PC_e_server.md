# Cora — roadmap prova PC e installazione finale server

Aggiornata il 15 settembre 2026.

## Decisione di progetto

Il lavoro attuale sul PC Windows è un **proof of concept temporaneo**. Serve per capire il repository JARVIS, verificare LangGraph, provare `gpt-oss:20b`, sperimentare gli agenti e raccogliere idee. Non deve diventare una configurazione di produzione.

La configurazione definitiva verrà progettata e installata successivamente sul server Debian. Durante la prova sul PC annoteremo decisioni, problemi, misure e idee utili alla versione finale.

## Essenziale adesso — prova sul PC

1. Conservare il container `ia-ollama` con Ollama 0.34.1 e `gpt-oss:20b`.
2. Mantenere il collegamento JARVIS/LangGraph → Ollama locale.
3. Usare l'interfaccia Streamlit per prove manuali.
4. Rendere chiara l'identità di Cora e impedire che dichiari falsamente di essere GPT-4.
5. Provare il routing supervisore → agenti e almeno uno strumento completamente locale.
6. Sostituire o disabilitare Tavily/Groq/Gemini e ogni funzione che richieda token LLM cloud.
7. Lasciare Gmail e Calendar opzionali: la loro assenza non deve bloccare l'avvio.
8. Misurare tempi di risposta, RAM, CPU e stabilità. Stato rilevato: `gpt-oss:20b` usa circa 13,3 GB ed è eseguito al 100% su CPU nel container Windows.
9. Annotare problemi, modifiche al repository e idee emerse durante le prove.

Non è essenziale ora: memoria definitiva, sicurezza di produzione, accesso remoto, avvio permanente, database definitivo, GPU perfettamente configurata o containerizzazione completa dell'interfaccia.

## Da progettare nella versione finale sul server

1. Architettura Docker Compose riproducibile e versionata.
2. FastAPI come API centrale e LangGraph come orchestratore.
3. PostgreSQL + pgvector come memoria persistente; Redis per code, stato e timeout.
4. Langfuse per tracce, latenza, errori, costi computazionali e valutazione degli agenti.
5. n8n come strato di automazione, senza trasformarlo nel cervello del sistema.
6. Modelli locali selezionati in base ai compiti e alle risorse del server.
7. PC principale come worker opzionale: il server può chiedergli aiuto per compiti pesanti quando è online.
8. Heartbeat, registro delle capacità, timeout, fallback e coda dei lavori per il worker remoto.
9. Tailscale o rete privata; autenticazione e autorizzazioni per ogni azione sensibile.
10. Memoria strutturata con provenienza, importanza, scadenza e separazione tra fatti, ipotesi e preferenze.
11. Strumenti locali o senza token per ricerca, file, calendario, email e automazioni; conferma umana per azioni irreversibili.
12. Interfaccia web/telefono, notifiche e successivamente voce con Whisper e Piper.
13. Backup, ripristino, aggiornamenti controllati, healthcheck e avvio automatico.
14. Benchmark degli agenti e politica di allocazione dinamica delle risorse (“pulsazione” tra pochi e molti agenti).
15. Integrazione con i servizi già presenti sul server senza compromettere Immich, Nextcloud, Samba e gli altri dati personali.

## Regola durante il proof of concept

Ogni nuova idea va classificata in una delle tre categorie:

* **Provare ora:** serve a verificare un principio fondamentale.
* **Annotare per il server:** utile, ma richiede architettura stabile o sicurezza.
* **Scartare:** duplica funzioni, aggiunge complessità senza valore o richiede cloud a pagamento.

## Criterio di chiusura della prova PC

La prova può considerarsi riuscita quando:

* Cora risponde stabilmente dall'interfaccia grafica;
* usa il modello locale corretto;
* il supervisore riesce a chiamare almeno un agente o strumento locale;
* l'assenza di credenziali cloud non provoca errori all'avvio;
* abbiamo misure indicative di velocità e consumo;
* le modifiche utili e i limiti osservati sono documentati per l'installazione sul server.

