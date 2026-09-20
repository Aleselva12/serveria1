# Cora — roadmap prova PC e installazione finale server

Aggiornata il 20 settembre 2026.

## Decisione di progetto

Il lavoro attuale sul PC Windows è un **proof of concept temporaneo**. Serve a verificare LangGraph, Ollama locale, routing multi-agente, strumenti locali ed esperienza utente prima della futura installazione sul server Debian.

La configurazione definitiva verrà progettata e installata successivamente sul server. Durante la prova sul PC annotiamo decisioni, problemi, misure e idee utili alla versione finale.

## Stato attuale del proof of concept

Cora usa:

- Supervisor LangGraph;
- Ollama locale tramite `gpt-oss:20b` configurabile;
- Local Research Agent per documenti locali e Word;
- Audio Agent per trascrizione, diarizzazione opzionale e analisi audio;
- Email & Quotes Agent per archivio Gmail, digest giornaliero, bozze e preventivi PDF;
- strumenti locali per calcolo, file di progetto e stato del sistema;
- Streamlit come interfaccia temporanea.

Non sono presenti Tavily, Groq, Gemini o altri LLM cloud nel percorso principale.

## Priorità immediata — prova sul PC

1. Verificare stabilità del Supervisor e routing verso i tre agenti.
2. Eseguire smoke test e test manuali con casi reali.
3. Misurare latenza, CPU, RAM e comportamento di `gpt-oss:20b`.
4. Testare Local Research Agent su documenti reali.
5. Testare Audio Agent su riflessione personale e telefonata reale.
6. Testare Email Agent su archivio Gmail reale e digest giornaliero.
7. Verificare generazione PDF dei preventivi.
8. Costruire una nuova esperienza utente più modulare della UI Streamlit attuale.
9. Documentare errori, modifiche e limiti emersi.

## Esperienza utente — prossimo blocco

La UI definitiva del proof of concept dovrebbe separare frontend e backend.

Direzione prevista:

```text
Frontend modificabile
        ↓
FastAPI
        ↓
Cora / LangGraph
        ↓
Agenti e strumenti
```

L'obiettivo è arrivare anche a un avvio semplice da desktop, senza legare l'architettura futura a Streamlit.

## Da progettare successivamente

- Agente Struttura per conoscere topologia, capacità, permessi e stato dei componenti.
- Agente Programmatore con accessi controllati a codice, test e modifiche.
- Automazione dei preventivi tramite cataloghi, listini, varianti e dati cliente strutturati.

## Versione finale sul server

1. Docker Compose riproducibile e versionato.
2. FastAPI come API centrale e LangGraph come orchestratore.
3. PostgreSQL + pgvector per memoria persistente.
4. Redis per code, stato e timeout.
5. Langfuse per tracce, latenza, errori e valutazione.
6. n8n come strato di automazione, non come cervello del sistema.
7. Modelli locali selezionati in base ai compiti e alle risorse.
8. PC principale come worker opzionale per attività pesanti.
9. Heartbeat, registro capacità, timeout, fallback e code di lavoro.
10. Tailscale o rete privata e autorizzazioni per azioni sensibili.
11. Memoria strutturata con provenienza, importanza, scadenza e distinzione tra fatti e ipotesi.
12. Interfaccia web/telefono e successiva integrazione voce.
13. Backup, ripristino, healthcheck e avvio automatico.
14. Benchmark agenti e allocazione dinamica delle risorse.
15. Integrazione senza compromettere Immich, Nextcloud, Samba e gli altri servizi del server.

## Regola del proof of concept

Ogni nuova idea va classificata come:

- **Provare ora**: verifica un principio fondamentale.
- **Annotare per il server**: utile ma richiede architettura più stabile.
- **Scartare**: aggiunge complessità senza valore sufficiente.

## Criterio di chiusura della prova PC

La prova può considerarsi riuscita quando:

- Cora risponde stabilmente dalla UI;
- usa il modello locale configurato;
- il Supervisor instrada correttamente i compiti;
- i tre agenti principali superano test reali;
- l'assenza di credenziali opzionali non blocca l'avvio generale;
- abbiamo misure indicative di latenza e consumo;
- esiste una UI modulare sufficiente per l'uso quotidiano;
- modifiche e limiti sono documentati per il passaggio al server.
