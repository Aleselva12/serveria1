# Prova Cora sul server attuale

Questa branch è **sperimentale** e non va mergiata in `main` durante il confronto.
Deriva dalla stessa versione PC usata come riferimento, ma adatta il deployment
alla macchina Debian attuale.

## Scelte del profilo

- modello unico: `qwen3:0.6b`;
- inferenza CPU;
- context 8192;
- output massimo 512 token;
- modello residente per 30 minuti;
- PostgreSQL pool ridotto a 2;
- background embeddings soltanto dopo 120 secondi di inattività, batch 1;
- niente profilo audio/Whisper al primo test;
- NAS reale montato come `/nas/drive` da `/srv/nas/Dati/drive`.

Il modello piccolo non serve a valutare la qualità finale di Cora: serve a
misurare il costo dell'architettura completa sulla macchina attuale.

## 1. Checkout

```sh
git clone -b server-test/current-hardware https://github.com/Aleselva12/serveria1.git cora-server-test
cd cora-server-test
```

Se la repository è già clonata:

```sh
git fetch origin
git switch server-test/current-hardware
```

## 2. Ollama host

Questa configurazione presuppone Ollama sull'host alla porta 11434. Verificare:

```sh
curl http://127.0.0.1:11434/api/tags
docker exec ollama ollama pull qwen3:0.6b
docker exec ollama ollama pull nomic-embed-text
```

Poiché l'API Cora gira in Docker, Ollama deve essere raggiungibile anche da
`host.docker.internal`. Il container Ollama già pubblicato con
`-p 11434:11434` normalmente soddisfa questo requisito.

## 3. Inizializzazione

```sh
python3 deploy/manage.py init
```

Controllare `deploy.env`. Per questo test lasciare:

```dotenv
CORA_API_BUILD_TARGET=api
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3:0.6b
```

Non attivare ancora `api-audio-cpu`: Whisper falserebbe il primo confronto di
RAM/CPU e aggiungerebbe un altro carico.

## 4. NAS

Il file `compose.server-test.yml` monta il NAS reale. Prima verificare:

```sh
test -d /srv/nas/Dati/drive
test -r /srv/nas/Dati/drive
test -w /srv/nas/Dati/drive
```

Per usare l'override durante il test:

```sh
docker compose --env-file deploy.env -f compose.yml -f compose.server-test.yml config --quiet
docker compose --env-file deploy.env -f compose.yml -f compose.server-test.yml up -d --build --wait
```

## 5. Controlli

```sh
docker compose --env-file deploy.env -f compose.yml -f compose.server-test.yml exec -T api python -m deploy.doctor
docker stats --no-stream
docker exec ollama ollama ps
free -h
```

## 6. Accesso tramite Tailscale

Il web resta legato a `127.0.0.1:8090` perché la porta 8080 è già usata da Nextcloud AIO sul server attuale. Per evitare esposizione WAN/LAN aperta:

```sh
sudo tailscale serve --bg http://127.0.0.1:8090
tailscale serve status
```

Impostare in `deploy.env` `CORA_UI_ORIGINS` sull'URL HTTPS Tailscale effettivo
e `CORA_COOKIE_SECURE=true`, quindi ricreare i container.

## 7. Cosa misurare

Per il confronto conservare almeno tre run:

1. domanda senza tool;
2. domanda che usa un tool deterministico, per esempio stato macchina;
3. delega al Local Research Agent su un piccolo documento.

In Attività → Profilazione annotare:

- tempo totale;
- attesa in coda;
- primo testo visibile;
- chiamate modello;
- token input/output;
- token/s;
- load duration;
- CPU/RAM osservate da Home e `docker stats`.

Non giudicare la qualità linguistica del modello 0.6B come qualità finale del progetto.


## Correzione dopo il primo run reale

Il primo tentativo con context 4096 ha fallito prima dell'inferenza con
`ContextOverflow`: prompt obbligatorio + schema delle capability del Supervisor
non entravano nel budget dopo la riserva output/tool. Per mantenere l'intero set
di capability nel test, il profilo server usa ora 8192 token invece di rimuovere
tool dal Supervisor.

La Home verifica inoltre i servizi già presenti sull'host tramite:
- Immich: `http://host.docker.internal:2283`
- Nextcloud: `http://host.docker.internal:11000`

Docker resta intenzionalmente non verificato dal backend: il container API non
riceve il socket Docker host solo per mostrare lo stato nella Home.
