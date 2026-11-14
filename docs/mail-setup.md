# Pagina Mail

Implementazione in sola lettura: Account A `aletessituraselva@gmail.com`, Account B `aleselva97@gmail.com`, vista Tutti. Nessun invio, modifica delle etichette, scheduler o avvio automatico del worker. I token Calendar e Gmail legacy non vengono migrati o sostituiti.

## Collegamento sul server

1. Nel progetto Google Cloud abilita Gmail API. Configura il consenso OAuth con scope `https://www.googleapis.com/auth/gmail.readonly`; se l’app è in Testing aggiungi entrambi gli indirizzi agli utenti di test. Le limitazioni Google per app in Testing possono richiedere nuove autorizzazioni periodiche.
2. Crea un client OAuth **Applicazione web**. Registra l’URI esatto `https://<origine-cora>/google-mail-callback.html` (inclusa eventuale porta HTTPS usata da Cora/Tailscale). Il callback è sulla stessa origine del frontend, senza `/backend`.
3. Custodisci il JSON del client sul server in `/state/gmail-web/web-credentials.json`, leggibile solo dal processo Cora. Non caricarlo nel repository o nel browser. Imposta nel `deploy.env` privato:
   - `CORA_GMAIL_STATE_DIR=/state/gmail-web`
   - `CORA_GMAIL_WEB_CREDENTIALS_PATH=/state/gmail-web/web-credentials.json`
   - `CORA_GMAIL_WEB_REDIRECT_URI=https://<origine-cora>/google-mail-callback.html`
4. Distribuisci backend e frontend insieme e riavvia Cora. Lo stato deve risiedere nel volume persistente `/state`, come Calendar. Proteggi directory e backup sul sistema host; su Windows applica ACL private.
5. Accedi a Cora come proprietario. Apri **Mail**, premi **Collega** per A e autorizza `aletessituraselva@gmail.com`. Torna alla pagina e ripeti per B autorizzando `aleselva97@gmail.com`. Un account diverso viene rifiutato prima di salvare il token. Usa la stessa scheda per completare ogni collegamento.

Un solo client Google può autorizzare entrambi gli utenti; le autorizzazioni, le sessioni PKCE e i file `a-token.json` / `b-token.json` restano distinti. Nessuna credenziale viene fornita o inventata da questa implementazione. Il browser conserva temporaneamente soltanto una chiave di completamento monouso, non i token Google. Le API riusano il controllo proprietario e le richieste autenticate di Cora. Da remoto occorre il normale login; il callback web usa la sessione cookie del sito.

## Riepiloghi e limiti

Scegli Account A, B o Tutti e l’ambito Posta in arrivo, Non lette o Ricevute ieri. Il riepilogo usa **oggetti e anteprime dei primi 20 messaggi per account**, non i corpi completi né tutti i messaggi paginati. Copertura limitata ed errori parziali sono indicati nell’interfaccia. La lista può caricare altre pagine; ogni messaggio apre dettagli e testo semplice. HTML non eseguito, allegati non scaricati; i messaggi solo HTML mostrano l’anteprima. La lettura non segna la mail come letta.

Assegna manualmente un modello worker all’agente Email attraverso l’infrastruttura Architettura/Macchine esistente. In assenza di assegnazione remota, con worker OFF o errore, la pagina restituisce uno stato controllato e permette di consultare le email. Nessun fallback locale, risveglio del PC o accodamento di inferenze. Gli input email sono trattati come dati non attendibili e il riepilogo non dispone di strumenti d’azione.

## Contratto per la futura pagina Automazioni

`GET /api/v1/mail/automation-template?selection=a|b|all` e il pulsante **Scarica bozza per Automazioni** producono un contratto JSON versione 1, `kind=mail.daily_summary`, `enabled=false`, `delivery=null`, orario `08:00`, fuso `Europe/Rome`, ambito `yesterday`. È un punto di integrazione, non un’automazione già importabile/eseguibile nell’editor attuale. Non viene salvato alcun job o destinatario e non viene inviato nulla.

Il futuro esecutore dovrà chiamare `POST /api/v1/mail/summary` con `{ "selection": "all", "scope": "yesterday" }`, gestire copertura/parzialità, scegliere esplicitamente destinazione e modalità di consegna, persistenza, attivazione e deduplicazione. L’intervallo di ieri è mezzanotte locale inclusa fino alla mezzanotte corrente esclusa, rispettando giornate di 23/25 ore e convertendo i limiti in timestamp per Gmail. Per un riepilogo completo del giorno occorrerà estendere l’attuale limite di copertura.

Riferimenti Google: https://developers.google.com/workspace/gmail/api/guides/list-messages e https://developers.google.com/workspace/gmail/api/reference/rest/v1/users/getProfile

## Verifica locale del 14 novembre 2026

- Frontend: 211 test passati, inclusi OAuth Mail, selezione account, risposta tardiva del dettaglio e worker non disponibile. Build produzione riuscita; resta l’avviso Vite sulle dimensioni dei bundle.
- Backend: `tests.test_mail`, `tests.test_google_calendar`, `tests.test_calendar`: 34 test, esito OK, 7 saltati per prerequisiti del relativo ambiente.
- Verifica estesa con `tests.test_google_calendar_web_auth`: 45 test, 7 saltati e 2 fallimenti nei test Calendar preesistenti che confrontano mode Unix 0600 con i permessi riportati da Windows (0666). Nessuna modifica ai test Calendar per mascherare questa differenza; verificare i permessi anche sull’host Linux di produzione.
- Nessuna prova OAuth/Gmail reale, inferenza worker reale, distribuzione o test visivo sul browser del server: mancano le credenziali e le autorizzazioni reali degli account. I test dei provider usano simulazioni.

## Integrazione con main del 15 novembre 2026

Risolti i conflitti in api.py e deploy/deploy.env.example preservando la riorganizzazione di main. Mail risiede ora in core/api/mail_api.py e core/domain/mail*.py. Verifica dopo integrazione: 235 test frontend passati, build produzione riuscita; suite backend Mail/Calendar 34 test OK con 7 saltati.
