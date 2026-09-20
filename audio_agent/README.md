# Cora Audio Agent

L'Audio Agent lavora esclusivamente su file audio locali autorizzati.

## Capacità

- trascrizione locale con `faster-whisper`;
- timestamp della trascrizione;
- supporto per note vocali e riflessioni personali;
- supporto per telefonate e conversazioni;
- diarizzazione opzionale con un modello `pyannote` locale;
- riassunto e analisi solo dopo la trascrizione e solo quando richiesti;
- salvataggio opzionale della trascrizione in `.txt`.

Formati accettati:

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

Se si usa un semplice nome modello e quel modello non è già nella cache locale, `faster-whisper` può tentare di recuperarlo. Per un'installazione completamente offline, indicare quindi un percorso locale.

### Diarizzazione

```env
CORA_DIARIZATION_MODEL=/percorso/al/modello/pyannote/locale
```

Se il modello non è configurato o la diarizzazione fallisce, Cora produce comunque la trascrizione senza attribuire battute a speaker specifici.

Le etichette sono solo `Interlocutore 1`, `Interlocutore 2`, ecc. L'identità reale non viene dedotta automaticamente.

### Cartelle

Audio autorizzati:

```env
CORA_AUDIO_ROOT=/srv/cora/audio
```

Trascrizioni salvate:

```env
CORA_TRANSCRIPT_ROOT=/srv/cora/audio/_transcripts
```

L'Audio Agent non può uscire dalle directory autorizzate.

## Output tecnico

`transcribe_audio_file` restituisce uno stato strutturato con:

- `status`;
- file sorgente;
- lingua rilevata;
- durata;
- numero di segmenti;
- stato della diarizzazione;
- numero speaker rilevati, quando disponibile;
- trascrizione.

La trascrizione non viene duplicata in una seconda struttura segmentata, così le conversazioni lunghe occupano meno contesto.

## Stato dell'agente

Lato codice l'agente è considerato completo per il proof of concept.

Restano da verificare con test reali:

1. qualità della trascrizione su voce singola;
2. qualità su telefonata registrata;
3. diarizzazione a due speaker;
4. prestazioni CPU/RAM e tempo di elaborazione;
5. scelta finale del modello Whisper e del modello pyannote per il server.
