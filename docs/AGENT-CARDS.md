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
