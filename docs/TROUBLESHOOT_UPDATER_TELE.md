# Diagnostica aggiornamenti e Magazzino Tele — Debian serverale

Gli indirizzi Tailscale della macchina sono equivalenti:
- IPv4: `100.112.253.3`
- MagicDNS: `serverale.tail7b83c3.ts.net`
- Portale updater esistente mostrato dal proprietario: `https://serverale.tail7b83c3.ts.net:8443` (verificare che HTTPS e portale siano ancora attivi)
- Tele dopo il deploy: `http://100.112.253.3:8082` (NON raggiungibile finché il web server non ascolta).

## Diagnosi non distruttiva

Da SSH su Debian:

```sh
sudo systemctl status cora-updater --no-pager
sudo ss -lntp | grep -E ':(8443|8082|8080|9021)\\b' || true
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
sudo test -f /srv/cora-updater/config.json && echo 'Updater configurato' || echo 'Updater config non trovata'
sudo test -d /srv/apps/magazzino-tele && echo 'Tele checkout presente' || echo 'Tele non installato'
```

Non incollare `config.json`, `deploy.env` o il contenuto di file `.env` nei ticket/chat: contengono segreti.

## Pulsante Aggiorna Cora

La Home legge `CORA_UPDATE_URL` dal processo API; il backend lo valida HTTPS. Se la pagina host esistente funziona su 8443, impostare la seguente voce nel **file di ambiente effettivamente usato dal Compose Cora**, normalmente `deploy.env`, mantenendo le altre variabili e senza pubblicare il file:

```env
CORA_UPDATE_URL=https://serverale.tail7b83c3.ts.net:8443
```

Poi ricreare l'API Cora con il percorso di deployment già installato, non con un Compose improvvisato. Non confondere `CORA_UPDATE_URL` (link browser HTTPS) con `CORA_UPDATER_URL` (bridge privato API ↔ updater host). La pagina HTTPS 8443 va verificata prima di salvarla.

## Pulsante Gestisci applicazioni

La UI non abilita il sistema: il gestore vive nel codice `updater/installed` copiato durante il provisioning, separato dai container Cora. Occorre installare la nuova versione dell'updater host seguendo `updater/README.md`, a servizio fermo e preservando configurazione, token e repository Git. Non sostituire l'intera directory o il `config.json` con quello del repository.

L'opzione in `/srv/cora-updater/config.json` per la nuova versione è `"managed_apps_enabled": true`, soltanto dopo aver controllato `"managed_apps_root"` (predefinito `/srv/apps`), permessi e allowlist. Riavviare poi `cora-updater` e verificare il log.

**Attenzione:** un clone da pulsante di Tele installa soltanto i sorgenti se mancano `deploy/.env` e `deploy/init/01-schema.sql`. Deve restare nello stato `needs_configuration` finché l'amministratore non crea quei file. Non presume che un clone equivalga a un servizio HTTP avviato.

## Prima accensione Tele

In `Aleselva12/magazzino-tele`, `deploy/README.md` contiene i passi per:
1. Estrarre SOLO il DDL dal backup storico con `python3 deploy/prepare_schema.py`. Nessun cliente, ordine, colore o altro record precaricato.
2. Preparare `deploy/.env` privatamente con indirizzo `100.112.253.3` e due credenziali MySQL nuove.
3. Verificare `docker compose --env-file deploy/.env -f deploy/compose.yml config` prima di avviare.
4. Eseguire `docker compose --env-file deploy/.env -f deploy/compose.yml up -d --build` e poi controllare `ps`, log web e `http://100.112.253.3:8082/health` da un dispositivo Tailscale autorizzato.

Non esporre la porta su WAN, non copiare dump clienti in GitHub e non aprire la GUI alla zia prima delle verifiche minime di importazione Excel e backup.

## Limiti

Questo documento non attesta accesso SSH al server o funzionamento del portale HTTPS. Il nuovo servizio web Tele non è collegato a Cora né alle sue autorizzazioni agentiche.
