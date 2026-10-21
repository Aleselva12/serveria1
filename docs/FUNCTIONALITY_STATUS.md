# Registro funzionale Cora (stato verificabile)

Gli stati sono distinti: **codice presente**, **test automatici**, **operativo sul Debian**.
Non usare "operativo" in base alla sola presenza di file, pulsanti o check CI.

## Audio — controllo 2026-10-21

- UI: `frontend/src/components/Audio.tsx`; API: `core/audio_api.py`; motore: `audio_agent/audio_tools.py`.
- Upload file audio registrati (da smartphone/PC): API POST `/api/v1/audio`. **Operativo per il caricamento**: confermato sul telefono dal file M4A presente in elenco.
- Elenco, dettagli, download audio, modifica/esportazione trascrizione, copia in Libreria IA: **implementati**, da collaudare end-to-end sul server.
- Trascrizione Faster-Whisper: **non operativa sul Debian al 21/10**; il runtime ha segnalato dipendenze audio non installate. Un tag o sha Docker non attesta il target di build.
- Disponibilità del modello: `/api/v1/audio/status`, ora richiede modello locale con manifest e checksum validi. Questo evita un falso "pronto" quando il modello potrebbe essere scaricato.
- Diarizzazione: opzionale e distinta; non promettere identificazione certa degli interlocutori.
- Analisi LLM delle trascrizioni -> appunti strutturati -> file NAS: **da implementare**, con approvazione prima di modificare/spostare file originali.
- Trascrizione automatica al caricamento: **non implementata**; il pulsante resta esplicito.
- Per passare a operativo: controllare `CORA_API_BUILD_TARGET=api-audio-cpu` nel `deploy.env` reale, installare il modello con `python3 deploy/manage.py audio-model small`, confermare `python3 deploy/manage.py audio-check`, avviare API con configurazione Compose corretta e trascrivere un M4A di prova.
- Il modello Whisper non può essere attivato da una semplice modifica al frontend. Conservare dati e servizi NAS fuori dal deploy Cora.

## Regola di completamento
1. Ispezionare codice e deploy esistenti.
2. Documentare dipendenze, API e consenso/permessi.
3. Test automatici della modifica senza saltare controlli.
4. Collaudo su Debian e browser telefono; registrare commit e risultato.


## Aggiornamenti Cora — verifica 2026-10-21

- La Home mostra esclusivamente il commit attivo e un collegamento alla sottopagina interna `#updates`.
- La sottopagina interroga le API autorizzate di Cora ogni 3 secondi, anche durante una temporanea indisponibilità del backend. **Non è una seconda interfaccia pubblica dell'updater** e non espone token.
- Durante il riavvio dei container, lo stato mostrato è esplicitamente **ultimo dato noto, non verificato**. L'updater sul Debian continua a lavorare e la pagina riprende la lettura quando FastAPI torna disponibile.
- I rilasci `ready` di una versione base differente dal commit attivo non sono installabili dall'interfaccia.
- Un POST con esito non confermato **non viene ripetuto automaticamente**.
- Percorso di aggiornamento host in un comando (da usare solo dopo merge e CI verde della PR):

```sh
cd /srv/cora-server-test && git fetch origin main && git merge --ff-only origin/main && sudo python3 deploy/update_once.py --commit "$(git rev-parse HEAD)"
```

  `deploy/update_once.py` verifica il target `api-audio-cpu`, l'assenza di altri job attivi, la corrispondenza esatta del commit proveniente dal repository configurato; chiede al servizio host di preparare, testare e poi applicare il rilascio, aspettandone l'esito. Backup e ripristino restano responsabilità dell'updater, non del checkout Git. Non usare `docker compose down -v`.
- La pagina e il comando devono essere collaudati sul Debian dopo la CI; non indicare operativo senza verifica.
