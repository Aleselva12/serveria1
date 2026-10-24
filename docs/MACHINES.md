# Cora: Macchine e selezione manuale dei modelli Ollama Windows

## Stato e limiti

- Debian e Docker Windows si raggiungono già mediante Tailscale Serve.
- Un container `worker` (128 MiB RAM) espone la piccola API di controllo; NON
  esegue LLM, non accede alla GPU, al filesystem di Windows o al Docker Engine.
- Ollama viene installato **sull'host Windows**: è Ollama a usare la Radeon RX 6800
  (16 GB VRAM nominali) e la RAM di sistema secondo driver, contesto e modello.
- La pagina Macchine mostra tutti i modelli installati nell'Ollama del desktop e
  permette al proprietario di selezionarne esattamente uno, con ON/OFF. Non ci sono tool
  agentici che possano modificare questi parametri. I modelli non vengono
  scaricati automaticamente e non restano obbligatoriamente in memoria.
- L'interruttore OFF blocca le chiamate di inferenza tramite Cora, non arresta
  Ollama sul PC e non arresta Docker: è una configurazione applicativa.
- Il pulsante **Prova inferenza** invia una sola richiesta fissa tramite l'API
  autenticata di Cora. Non sono implementati code o scheduler. Dalla pagina Architettura è possibile
  assegnare manualmente l’inferenza di un agente al modello del profilo attivo
  del worker (richiede il bridge aggiornato, vedi `AGENT-CARDS.md`).

## 1. Desktop Windows: Ollama

Installare Ollama Windows da https://ollama.com/download/windows e avviarlo.
L'accelerazione AMD su Windows può usare il backend Vulkan (dipende da driver
e versione Ollama); evitare di promettere che ogni modello userà tutta la VRAM.

Da PowerShell, per vedere i modelli locali:

```powershell
ollama list
curl.exe http://127.0.0.1:11434/api/tags
```

Per installare inizialmente i tre modelli (circa 27 GB complessivi **su disco**,
non contemporaneamente in VRAM), eseguire a scelta, anche uno alla volta:

```powershell
ollama pull gpt-oss:20b
ollama pull qwen3:8b-q8_0
ollama pull qwen3:4b-q8_0
```

Pesi stimati: 14 GB, 8.9 GB, 4.4 GB. Servono ulteriore memoria per cache,
contesto e runtime. `gpt-oss:20b` è un obiettivo da provare, **non garanzia**
che il modello resti interamente nei 16 GB della RX 6800.

## 2. Autenticazione del worker

Usare un token segreto random di almeno 32 caratteri **identico** nel
container Windows e nel backend Cora, mai nel repository Git o nella chat.
Da PowerShell nella cartella `worker`:

```powershell
$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$rng.Dispose()
$token = ([BitConverter]::ToString($bytes)).Replace("-","").ToLowerInvariant()
Set-Content -Path .env -Value ("CORA_WORKER_TOKEN=" + $token) -Encoding ascii
```

Nel Debian aggiungere il valore `CORA_WORKER_SHARED_TOKEN=...` nel **file
privato `deploy.env`** usato dal container API Cora. Aggiungere anche
`CORA_TAILSCALE_DNS_SUFFIX=tail7b83c3.ts.net`. Mai scrivere i token in
`compose.yml`, GitHub o `.env.example`.

> Per ora è un token comune al primo worker. Prima di collegare macchine con
> proprietari diversi, implementare una credenziale distinta per dispositivo.

Nella cartella `worker` di Windows dopo `git fetch` e l'aggiornamento branch:

```powershell
docker compose up -d --build
curl.exe http://127.0.0.1:8765/health
```

Docker Compose legge automaticamente il file `.env` per la variabile
`CORA_WORKER_TOKEN`. Non mostrare il contenuto del file in chat.

Il backend Debian deve essere riavviato tramite la normale procedura di
aggiornamento dopo avere modificato il proprio `deploy.env`.

## 3. Ollama Windows raggiungibile dal container

Il worker usa `http://host.docker.internal:11434` per parlare con Ollama.
Dopo l'installazione e l'avvio di Ollama eseguire:

```powershell
docker exec cora-desktop-worker python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags',timeout=5).status)"
```

Se risponde 200 la connessione è pronta. Se la connessione è rifiutata,
la causa può essere il binding `127.0.0.1` di Ollama. **Non esporre alla
cieca la porta 11434 sulla LAN o tailnet**, perché l'API Ollama non usa
autenticazione nativa. Prima valutare le opzioni di networking Docker e una
regola firewall Windows stretta verso la sola rete interna Docker. Configurare
`OLLAMA_HOST=0.0.0.0:11434` solo dopo aver verificato e limitato il firewall,
chiudendo e riaprendo completamente Ollama.

Controllare l'effettiva collocazione GPU/CPU durante un test con
`ollama ps` su Windows. Se il driver AMD non attiva l'accelerazione, il
worker funziona ugualmente ma inferenza e velocità possono essere peggiori.

## 4. Tailscale

Mantenere sul desktop la configurazione già verificata:

```powershell
tailscale serve status
```

Il worker è pubblicato da Tailscale Serve **non Funnel**, sulla porta HTTPS
della tailnet; il container Docker pubblica solo su `127.0.0.1:8765`.
Rafforzare con Tailscale Grants: solo Debian e amministratori autorizzati
possono chiamare l'endpoint della macchina.

Dal Debian (host e poi container API):

```bash
curl https://desktop-q8ptjrm.tail7b83c3.ts.net/health
API=$(docker ps -q --filter "label=com.docker.compose.service=api" | head -n 1)
docker exec "$API" python -c "import urllib.request;print(urllib.request.urlopen('https://desktop-q8ptjrm.tail7b83c3.ts.net/health',timeout=10).read().decode())"
```

## 5. Pagina Macchine

Aprire **Macchine** dopo aver installato la PR. Registrare:
- Nome: Desktop
- FQDN: `desktop-q8ptjrm.tail7b83c3.ts.net`

Alla prima registrazione lo stato è **OFF** e nessun modello viene
selezionato né avviato automaticamente. Apri il riquadro **Desktop →
Gestisci modelli e risorse** per:
1. Leggere l'elenco completo dei modelli già installati da Ollama Windows,
   con la dimensione dei pesi su disco. Comprende anche i modelli di coding,
   per esempio `qwen3-coder:30b-a3b-q4_K_M`, se presenti in `ollama list`.
2. Selezionare esattamente un modello dal menu a tendina o dalla lista radio.
   L'impostazione viene salvata sul server; non avvia subito il modello.
3. Attivare manualmente il worker su **ON** oppure mantenerlo **OFF**.
4. Premere **Prova inferenza**; il modello viene caricato da Ollama Windows
   quando la richiesta parte. Usa `ollama ps` sul PC per verificare RAM/VRAM.
5. Se un agente era associato a un modello diverso in Architettura,
   aggiornarne manualmente l'assegnazione: non esiste fallback o sostituzione
   automatica del modello.

Le impostazioni dei tre profili delle versioni precedenti rimangono nei dati
per compatibilità e migrazione, ma la pagina di selezione mostra un solo
modello attivo per worker. Nessun modello viene scaricato automaticamente.

La connessione del nodo resta visibile anche con la selezione OFF.
La registrazione, i profili e il selettore sono conservati in
`/state/machines.json` sul Debian con scrittura atomica.

## 6. Inventario Tailscale automatico (opzionale)

Per vedere tutti i dispositivi (anche non worker) configurare nel backend
`CORA_TAILSCALE_TAILNET`, `CORA_TAILSCALE_OAUTH_CLIENT_ID`,
`CORA_TAILSCALE_OAUTH_CLIENT_SECRET` con un client OAuth limitato
allo scope `devices:core:read`. Non servono per l'aggiunta manuale.

## Sicurezza e limiti di deploy

- Le chiamate a /models e /generate richiedono il segreto condiviso.
- La chiamata verso i worker è consentita solo nel suffisso Tailscale impostato
  dal backend e non segue reindirizzamenti HTTP.
- Nessun download modello, shell remota o accesso Docker è offerto dalla UI.
- Se un laptop è offline non viene eseguito alcun compito remoto.
- Il codice di questa PR **non modifica compose.yml di Cora** e non
  configura automaticamente credenziali, firewall o Ollama Windows.
- L'aggiornamento Cora potrebbe essere vincolato ai controlli dell'updater:
  verificare il normale processo di rilascio e l'accessibilità del `deploy.env`.
