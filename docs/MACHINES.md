# Macchine: primo collegamento Docker + Tailscale

Questa è la **fase di sola registrazione e raggiungibilità** dei nodi di Cora.
Non assegna ruoli, non avvia modelli, non esegue comandi remoti e non concede
accesso al Docker Engine o ai file del PC.

## Desktop Windows

1. Installare Docker Desktop (backend WSL2) e Tailscale sul **sistema host Windows**.
2. Accedere su Windows alla stessa tailnet del Debian, con MagicDNS abilitato.
3. In PowerShell:

   ```powershell
   git clone https://github.com/Aleselva12/serveria1.git
   cd serveria1\worker
   docker compose up -d --build
   curl.exe http://127.0.0.1:8765/health
   ```

   Per provare questo branch prima del merge, eseguire
   `git checkout feature/machines-tailnet-workers-20261024` **prima** di entrare in `worker`.

4. Da **PowerShell amministratore**, controllare prima la configurazione Serve:
   `tailscale serve status`. Non sovrascrivere altre condivisioni già attive.
   Con HTTPS abilitato nella tailnet eseguire:
   `tailscale serve --bg --https=443 http://127.0.0.1:8765`.
   **Usare Serve, non Funnel**, che renderebbe pubblico il servizio.
5. Controllare `tailscale serve status`; annotare il nome
   `nomepc.nometailnet.ts.net`. Dal Debian verificare:
   `curl https://nomepc.nometailnet.ts.net/health`.
6. In Cora > **Macchine**, registrare il FQDN trovato. Il worker resterà
   senza capacità configurate (`capabilities: []`).

**Nota**: Docker Desktop deve essere avviato perché il container sia disponibile.
I worker sulle future macchine potranno usare la stessa convenzione.

## Inventario automatico Tailscale (opzionale)

La pagina funziona anche senza accesso all'API Tailscale, usando registrazione manuale.
Per mostrare **tutti** i dispositivi della tailnet, creare dal pannello di
amministrazione Tailscale un OAuth client con solo scope
`devices:core:read`; inserire nell'ambiente **del backend Cora**:

- `CORA_TAILSCALE_TAILNET`: nome della tailnet nell'API (ad es. `example.com`).
- `CORA_TAILSCALE_OAUTH_CLIENT_ID`: client ID.
- `CORA_TAILSCALE_OAUTH_CLIENT_SECRET`: segreto.

Non inserire segreti nel repository o nell'interfaccia web. Le credenziali non
sono mai restituite al frontend. Sono necessari gli opportuni permessi
amministrativi Tailscale per creare il client.

La lista dei dispositivi Tailscale è **visibilità di rete**, non autorizzazione
a eseguire calcoli. Solo le macchine registrate come worker vengono sondate
sull'endpoint /health.

## Sicurezza

- Port 8765 esposto solo su localhost Windows; HTTPS tramite Tailscale Serve.
- Controllare Tailscale Grants per consentire l'accesso al worker dal solo server
  Cora e dagli amministratori autorizzati.
- Non aggiungere mount dell'host, `/var/run/docker.sock`, shell/exec generico o
  volumi con file personali al worker.
- I laptop offline compaiono nell'inventario ma non ricevono lavori.
- Prima di abilitare **qualsiasi capacità eseguibile** serviranno autentica
  applicativa, allowlist dei job, sandbox specifiche, limiti di risorse,
  audit e revoca.

## Test dell'integrazione

- Dal PC: `docker compose ps` e `curl.exe http://127.0.0.1:8765/health`.
- Dal server: `curl https://nomepc.nometailnet.ts.net/health`.
- Da Cora: pagina Macchine > Aggiungi worker > Aggiorna; lo stato deve
  indicare worker pronto, **zero capacità**.
- Spegnere Docker Desktop e verificare che Cora mostri il worker offline
  senza bloccare gli altri servizi.
