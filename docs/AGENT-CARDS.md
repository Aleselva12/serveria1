# Architettura: schede agenti e assegnazione dell'inferenza

La vista principale non mostra più il grafo. Ogni agente è un pulsante grande:
la scheda contiene nome, descrizione, stato runtime, disponibilità strutturale,
tool realmente collegati, controlli, modello e macchina di inferenza.
Il grafo generale e la sua modifica visuale restano un'idea futura.
Tools/bozze delle automazioni e Attività restano nelle rispettive viste.

Gli altri programmi sono elencati separatamente usando `/api/v1/system/status`:
servizi configurati e container visibili al backend. Nessun conteggio dimostrativo,
programma inventato o stato "installato" dedotto da una configurazione incompleta.
Se Docker non è accessibile al backend, il catalogo non è un inventario completo
 dei pacchetti del Debian. Gli URL sono quelli configurati per il browser.

## Scelta per agente

- `GET /api/v1/architecture/agents`: registro, tool e stato.
- `GET /api/v1/architecture/model-targets`: Ollama di Cora e worker registrati.
- `GET /api/v1/architecture/model-targets/{id}`: modelli disponibili.
- `PUT /api/v1/architecture/agents/{id}/model`: scelta manuale autenticata.

`machine_id=local` usa Ollama dell'istanza Cora. `machine_id=inherit` rimuove
l'assegnazione e torna al modello generale. Altrimenti l'ID identifica un worker
registrato. Il backend valida che il modello sia installato prima di salvare.
Le assegnazioni persistono atomicamente in `agent-models.json`, accanto al file
`CORA_RUNTIME_SETTINGS_PATH` (Compose: `/state/agent-models.json`). L'assegnazione
specifica prevale sulla scelta globale; le impostazioni generali continuano a
mostrare il modello generale e non quello di un agente assegnato a un worker.

Le nuove chiamate risolvono la configurazione corrente senza riavvio. Le chiamate
 già iniziate proseguono con la configurazione che hanno acquisito. Non sono
aggiunti tool agentici per cambiare modello, macchina, profili o ON/OFF.

## Desktop: aggiornamento necessario

Ricostruire **anche il container worker sul desktop**, non solo Cora sul Debian:

```powershell
# Dalla cartella worker della repository aggiornata sul desktop:
docker compose up -d --build
```

Il bridge aggiornato dichiara `agent_chat=true` in `/models` e accetta `/chat` con
lo stesso token di `/generate`. I messaggi e gli schemi dei tool attraversano
l'API nativa Ollama `/api/chat`; le chiamate ai tool tornano a Cora, che applica
i suoi strumenti e permessi. Solo l'inferenza viene spostata al desktop.
Whisper, memoria, file e gli altri tool non sono trasferiti al worker.

In Macchine viene elencato ogni modello già installato sul worker. Il proprietario
ne sceglie uno solo. Le vecchie impostazioni heavy/medium/light sono conservate
per compatibilità, ma non determinano più il modello dopo la selezione esplicita.
Se il worker viene spento, viene selezionato un modello diverso da quello assegnato
all'agente, oppure il modello sparisce, la chiamata remota fallisce esplicitamente:
nessun cambio modello, riattivazione o fallback automatico. OFF non annulla una
chiamata già partita. Il profilo `isolated` continua a bloccare l'inferenza remota.

La risposta remota è attualmente restituita completa, senza streaming token per token;
una sola inferenza per worker, timeout del bridge 300 secondi, corpo/risposta limitati
a 1 MB. Non sono introdotti scheduler o ripetizioni automatiche. Token, suffisso
Tailscale e modelli installati restano quelli configurati nella pagina Macchine.

I controlli di disponibilità non eseguono un LLM e non attestano che il modello
supporti ogni strumento: il collaudo con Ollama/hardware reali resta necessario.

## Configurato e osservato: verifica esplicita

Le sei definizioni di agente presenti sono:

| ID | Ruolo modello | Nodo LLM |
| --- | --- | --- |
| supervisor | supervisor | graph.call_model |
| structure_agent | structure | structure_agent.structure_graph.call_llm |
| programmer_agent | programmer | programmer_agent.programmer_graph.call_llm |
| local_research_agent | research | search_agent.search_graph.call_llm |
| audio_agent | audio | audio_agent.audio_graph.call_llm |
| email_quotes_agent | email | email_agent.email_graph.call_llm |

Tutti risolvono il modello attraverso `get_chat_model` a ogni chiamata. La chat
principale entra nel supervisore: cambiare solo Audio/Documenti/Mail non cambia
il supervisore. Cambia l'inferenza dello specialista quando effettivamente delegato.
La selezione generale salvata prevale sulle variabili dei ruoli senza assegnazione
specifica: questo può spiegare sei schede con lo stesso modello, senza significare
che siano sei istanze sempre caricate o sei agenti mancanti.

La risoluzione usa ora un solo snapshot di modello e macchina. Il salvataggio
restituisce una versione della configurazione; il frontend rilegge il catalogo e
confronta la versione prima di confermare. Ricarica configurazione e stato aggiorna
anche il modulo aperto e la health della chat. Non richiede restart per i LLM;
modificare codice/prompt Python richiede il normale aggiornamento di Cora.

`POST /api/v1/architecture/agents/{id}/verify` mette nel runtime una breve inferenza
senza tool. La UI ne segue l'esito e mostra il nome restituito dal provider. Non è
un collaudo di tutti i tool dell'agente, né una prova della collocazione GPU/CPU.
Se la configurazione cambia mentre la prova è in coda, la prova fallisce senza
usare una selezione diversa. Non viene eseguita alcuna prova al semplice refresh.

Le risposte native Ollama, locali e remote, aggiornano una cache bounded con
l'ultima osservazione per ruolo (`model-observations.json`, accanto alle impostazioni).
Contiene solo ruolo, modelli richiesto/riportato, macchina, timestamp, run e versione:
nessun prompt o testo generato. È uno stato riepilogativo, non un secondo log.
Le stesse osservazioni entrano nelle metriche del run persistito. Attività distingue
il modello configurato all'avvio dai modelli realmente riportati dai provider.
I nuovi messaggi chat non prendono più model_id dalla configurazione riletta a fine
risposta: usano il nome osservato nell'ultima chiamata, se disponibile. Le vecchie
esecuzioni non vengono ricostruite né considerate retroattivamente verificate.

## Audio: due motori distinti

Il ruolo `audio` sceglie il LLM per analisi e strumenti; la trascrizione usa invece
Faster-Whisper con `CORA_WHISPER_MODEL`, `CORA_WHISPER_DEVICE` e
`CORA_WHISPER_COMPUTE_TYPE`. La diarizzazione usa il modello locale
`CORA_DIARIZATION_MODEL`, se configurato. La scheda mostra separatamente modello
Whisper configurato e configurazione del motore caricato nella cache Python.

`POST /api/v1/audio/engine/reload` svuota la cache Whisper solo se lo slot runtime
è libero; non esegue un download né una trascrizione. Il motore si carica al prossimo
uso. Cambiare variabili Docker richiede comunque di ricreare/riavviare il container.
Assegnare un LLM sul desktop non trasferisce Whisper, diarizzazione o tool al desktop.

## Salvataggio con un worker precedente al bridge chat

L'assenza di `agent_chat=true` non disabilita più il pulsante Salva né impedisce
la persistenza di un modello installato e selezionato manualmente. La scheda
conferma il salvataggio e distingue l'assegnazione dalla possibilità di eseguirla.
Una verifica o una chat con il vecchio worker restituisce un errore esplicito di
aggiornamento: non usa `/generate` come sostituto dei messaggi/tool nativi e non
ripiega sul modello locale. ON/OFF, selezione del proprietario e profilo isolated
continuano a essere rispettati.

`GET /api/v1/architecture/worker-update`, protetto dall'accesso applicativo come
le altre route Architettura, restituisce uno ZIP dei soli `worker.py`, `Dockerfile`,
`compose.yml` e `UPDATE.md` della release installata. Non contiene file `.env` o
credenziali e non esegue comandi sul PC. La scheda espone download e istruzioni
per ricostruire il container esistente sul desktop. Dopo l'aggiornamento, Ricarica
modelli rilegge la compatibilità: l'assegnazione già salvata resta valida e non
richiede un riavvio di Cora. Il collaudo con l'hardware reale resta da eseguire.
