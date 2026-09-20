# Cora Email & Quotes Agent

L'agente gestisce tre aree:

1. ricerca e lettura dell'archivio Gmail;
2. riepilogo delle email di una giornata;
3. preparazione di preventivi commerciali e generazione PDF locale.

## Ricerca email

Il tool `search_email_archive` usa la sintassi di ricerca Gmail e restituisce contenuto, mittente, destinatario, data, oggetto e ID del messaggio.

Esempi concettuali:

```text
from:cliente@example.com ombrelloni
subject:preventivo Rossi
after:2026/09/01 before:2026/10/01 consegna
```

## Digest giornaliero

`get_daily_emails` recupera i messaggi di una data. L'LLM li sintetizza evidenziando richieste, decisioni, scadenze, promesse e follow-up.

## Scrittura email

L'agente può scrivere testo email. Non invia automaticamente.

`save_email_draft` salva una bozza Gmail soltanto se l'utente lo richiede esplicitamente.

## Preventivi PDF

`generate_quote_pdf` riceve righe strutturate con descrizione, quantità e prezzo unitario, calcola imponibile/IVA/totale e salva il PDF localmente.

Cartella configurabile:

```env
CORA_QUOTE_ROOT=./quotes
```

I prezzi o le condizioni mancanti non devono essere inventati dall'agente.

## Gmail OAuth

Percorsi configurabili:

```env
CORA_GMAIL_CREDENTIALS_PATH=./email_agent/credentials.json
CORA_GMAIL_TOKEN_PATH=./email_agent/token.json
```

Questi file non devono essere versionati su Git.
