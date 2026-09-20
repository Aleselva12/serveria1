# Cora Audio Agent

L'Audio Agent lavora esclusivamente su file audio locali autorizzati.

## Capacità

- trascrizione locale con `faster-whisper`;
- timestamp della trascrizione;
- supporto per note vocali e riflessioni personali;
- supporto per telefonate e conversazioni;
- diarizzazione opzionale con un modello `pyannote` locale;
- riassunto e analisi solo dopo la trascrizione e solo quando richiesti.

Formati attualmente accettati:

`.wav`, `.mp3`, `.m4a`, `.mp4`, `.aac`, `.flac`, `.ogg`, `.opus`, `.webm`.

## Configurazione

Le variabili principali sono documentate in `.env.example`.

### Whisper

Per una prima prova CPU:

```env
CORA_WHISPER_MODEL=small
CORA_WHISPER_DEVICE=cpu
CORA_WHISPER_COMPUTE_TYPE=int8
```

`CORA_WHISPER_MODEL` può anche contenere il percorso di un modello Whisper già scaricato localmente.

Importante: se si usa un semplice nome modello e quel modello non è già nella cache locale, `faster-whisper` può tentare di recuperarlo. Per un'installazione completamente offline, indicare quindi un percorso locale.

### Diarizzazione

La separazione degli interlocutori è opzionale.

```env
CORA_DIARIZATION_MODEL=/percorso/al/modello/pyannote/locale
```

Se il modello non è configurato o la diarizzazione fallisce, Cora deve comunque produrre la trascrizione e dichiarare che non ha potuto separare con affidabilità gli speaker.

Non vengono assegnate identità reali alle voci automaticamente. Le etichette sono solo `Interlocutore 1`, `Interlocutore 2`, ecc., salvo che l'identità sia fornita esplicitamente dall'utente o da metadati affidabili.

## Cartella audio

La directory autorizzata è controllata da:

```env
CORA_AUDIO_ROOT=/srv/cora/audio
```

L'Audio Agent non può uscire da questa radice.

## Dipendenze

```bash
pip install -r requirements.txt
```

Le dipendenze principali dell'agente sono:

- `faster-whisper`
- `pyannote.audio`

Il modello di diarizzazione non viene salvato nel repository Git.
