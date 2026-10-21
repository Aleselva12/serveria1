# Terminale personale del server

Nella pagina **Programma → Terminale del server** il proprietario può aprire una
shell SSH interattiva di Debian, anche dal telefono (Ctrl+C, Tab, frecce e Invio
sono disponibili come pulsanti). Non serve scegliere un workspace o avviare Ollama.

Il terminale richiede l'identità Tailscale già autorizzata per Cora e, a ogni
connessione, la password dell'utente Debian configurato. Non usa la vecchia
password di Cora. L'agente programmatore non ha un tool per questo servizio.

## Attivazione una tantum sul server

Prerequisiti: Cora già accessibile dal proprio URL HTTPS `*.ts.net` mediante
Tailscale Serve e login Tailscale; OpenSSH server attivo sulla porta 22 e
raggiungibile dalla rete Docker; un utente Debian non root con password SSH.
Le configurazioni con sola chiave SSH non sono supportate da questa prima versione.
Non modificare globalmente la configurazione SSH per abilitarlo senza prima
valutare gli altri accessi al server. Non aprire nuove porte sul router.

Dal checkout usato dall'installazione attiva, dopo aver aggiornato il codice:

```sh
sudo python3 deploy/terminal_setup.py --user ale
```

Sostituire `ale` con il nome effettivo (Linux distingue maiuscole/minuscole;
questa configurazione accetta i normali nomi utente minuscoli). Lo script legge
la chiave **pubblica** locale `/etc/ssh/ssh_host_ed25519_key.pub`, la fissa in
`/srv/cora-tools/terminal/known_hosts`, verifica Serve e prepara `deploy.env`.
Non chiede né salva password, non avvia container e non modifica sshd, sudo,
Tailscale o il firewall. Stampa il comando Compose completo da eseguire,
preservando tutti gli override dell'installazione, incluso `compose.terminal.yml`.

In Cora: aprire **Programma → Terminale del server**, inserire la password Debian
e premere **Connetti**. Per i privilegi amministrativi utilizzare `sudo` nella
shell: valgono le regole sudoers già impostate sul server. Se l'utente appartiene
al gruppo docker o ha NOPASSWD, possiede già privilegi equivalenti a root:
questa funzione non li riduce e non può garantire una seconda richiesta password.

Un terminale non configurato mostra istruzioni senza impedire l'uso del programmatore.
La modalità desktop HTTP non abilita il terminale: dal PC usare lo stesso URL Tailscale.

## Confini e comportamento

- Servizio Docker separato, non root, filesystem in sola lettura, nessuna porta
  pubblicata, nessun mount di dati Cora, repository, chiavi private o socket Docker.
- Nginx inoltra l'identità soltanto dal proxy Serve già fidato e aggiunge il suo
  segreto privato; il servizio richiede entrambi. Header falsificati da LAN/Internet
  non autorizzano l'accesso. Sono accettate connessioni WebSocket solo dall'origine
  HTTPS configurata; host, porta e utente SSH sono fissi, mai forniti dal browser.
- Verifica obbligatoria della chiave host SSH. Una chiave cambiata blocca l'accesso;
  verificare sul server la causa prima di ripetere il setup. Nessuna accettazione automatica.
- Password solo in memoria per l'autenticazione SSH e mai in URL o log. Nessuna
  registrazione di input/output o persistenza browser della console. La shell Debian
  può comunque conservare la propria cronologia, secondo la configurazione dell'utente.
- Massimo due connessioni contemporanee e cinque tentativi ogni cinque minuti,
  anche se riusciti. Ogni sessione termina dopo cinque minuti senza input o trenta
  minuti complessivi; l'output di un comando non rinnova l'inattività.
- Disconnessione/uscita dalla pagina chiude SSH. Per lavori persistenti usare `tmux`.
  Il sistema non promette di fermare processi che l'utente ha deliberatamente avviato
  in background. Il blocco dello schermo può sospendere la rete del telefono.
- Una revoca Tailscale blocca nuove connessioni; non è previsto un controllo continuo
  dell'identità dentro una sessione SSH già aperta. Per revocare immediatamente tutte
  le sessioni fermare il container terminale.

Il terminale aumenta l'impatto di eventuali vulnerabilità della pagina web (ad esempio
XSS) mentre è aperto. L'accesso indipendente SSH e il servizio separato riducono i
privilegi permanenti dell'applicazione; non rendono sicuro un browser o server già
compromesso. Controllare in Tailscale le regole di accesso al server: l'app non modifica
la policy della tailnet. Non attivare Funnel per questo servizio.

## Aggiornamento e disattivazione

L'immagine del terminale è indipendente dai rilasci API/web dell'updater. Per
aggiornarla, ripetere il comando Compose stampato dal setup con il nuovo checkout.
L'updater continua ad aggiornare API/web; non aggiorna automaticamente questo servizio.
Preservare l'override `compose.terminal.yml` nelle operazioni Compose manuali.
Per disattivarlo immediatamente: `docker stop cora-terminal-1` (adattare il nome se
il progetto Compose è diverso). Per disattivarlo in modo permanente, fermare e
rimuovere il servizio tramite Compose e omettere l'override nelle successive operazioni.

## Verifica

```sh
python -m pip install --require-hashes -r terminal_service/requirements.lock
python -m pip install httpx2
python -m unittest discover -s terminal_service -p 'test_*.py' -v
cd frontend && npm ci && npm test && npm run build
```

I test esercitano identità/origine, password e chiave host con un server SSH locale
sacrificabile, relay input/output, limiti e chiusura. Il collaudo sul server reale
richiede la configurazione SSH e Tailscale dell'installazione e resta distinto dalla CI.
