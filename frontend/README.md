# Frontend Cora

Interfaccia React/TypeScript/Vite di `serveria1`, nella stessa repository del backend. La vecchia repository frontend è archiviata. Installazione: `npm ci`; sviluppo: `npm run dev`; verifica: `npm test` e `npm run build`.

La compilazione deve funzionare anche sul server Intel Core i3-2100 (Sandy Bridge,
AVX ma senza AVX2). Dopo un arresto `Illegal instruction` durante la build con
Vite 8, la toolchain torna a Vite 6.4.6 e Plugin React 4.7.0; restano gli
aggiornamenti di sicurezza Python/Nginx e le dipendenze applicative aggiornate.
Il workflow `Frontend CPU compatibility` compila con CPU Sandy Bridge emulata,
incluso il processo separato esbuild. Un futuro aggiornamento della toolchain
deve superare anche questa prova; una build su runner moderni non basta a
dimostrare la compatibilità con il server. L'esatta istruzione responsabile
del precedente arresto non è stata identificata sul server.

Il proxy Vite inoltra `/backend/*` a `http://127.0.0.1:8000`. `CORA_API_TARGET` cambia la destinazione backend; `VITE_API_BASE_URL` cambia la base HTTP del browser. Per sessioni remote preferire UI e API sullo stesso sito; configurare l'origine nel backend. Non inserire chiavi o password in variabili Vite.

In modalità password il login personale riusa un cookie HttpOnly di sette giorni; desktop e Tailscale hanno percorsi distinti, dichiarati da `/auth/status`. `src/services/transport.ts` è il confine condiviso per cookie, header delle scritture e scadenza della sessione. `AuthGate` richiede il login, oppure consente la sola visualizzazione offline quando il backend non è raggiungibile. L'account iniziale si crea sul PC con `python -m core.auth`, come descritto nel README principale.

Pagine collegate: Home (sensori, servizi e stato), Chat (conversazioni, streaming e annullamento), File server/Libreria IA, Foto, Architettura (schede agenti, modelli per agente e programmi separati), Tools, Calendario, Macchine, Roadmap ad albero, Attività, Impostazioni, Gestione Memoria e Audio. Programma è collegato al Programmatore con workspace isolati e Copilot; la pagina Aggiornamenti usa invece il servizio updater host per preparare/applicare il main verificato. Nessuna di queste viste implica da sola che un servizio esterno sia installato o raggiungibile.

`src/services/runtimeApi.ts` crea il run prima di aprire SSE, separa testo provvisorio da risultato persistito e non ritenta automaticamente una scrittura dopo un errore di connessione. Un'interruzione del collegamento non prova che il run sia terminato: consultarne l'esito in Attività. Le vecchie API `/chat` restano per compatibilità.

Le proposte generiche e calendario sono visibili nel pannello comune. La conferma autorizza solo i parametri mostrati; gli esiti generici sono conservati. Le impostazioni di policy si applicano agli agenti, non alle modifiche manuali del proprietario.

Contratti TypeScript in `src/types/contracts.ts`; dettaglio integrazioni in [COLLEGAMENTI.md](COLLEGAMENTI.md). La descrizione autorevole dell'intero sistema è il README nella radice.


Gli allegati della chat e le funzioni avanzate dei file sono collegati. Per limiti, API, storage persistente e migrazione consultare il README principale e [COLLEGAMENTI.md](COLLEGAMENTI.md). Nessuna acquisizione dal microfono è necessaria.

## PWA e uso mobile

Il frontend è installabile come PWA tramite `public/manifest.webmanifest` e registra
`public/sw.js` con `src/services/pwa.ts`. L'obiettivo mobile principale è l'accesso
rapido a stato server, calendario, file/foto e caricamento audio. La PWA non trasforma
i servizi esterni in contenuti locali: Immich/Nextcloud continuano a essere raggiunti
tramite i rispettivi servizi e collegamenti.

Le notifiche Web Push usano una sottoscrizione del browser e le chiavi VAPID conservate
nel backend. Per iPhone/iPad e altri dispositivi serve un'origine HTTPS compatibile,
permesso notifiche e un collaudo reale sul dispositivo installato; il solo service
worker non prova che una notifica sia stata consegnata.

## Calendario e Google

La pagina Calendario funziona con due provider. Senza token Google usa PostgreSQL;
quando il token Calendar è presente, le letture e le operazioni manuali usano Google
Calendar. **Invia nuovi su Google** pubblica gli appuntamenti locali futuri non ancora
esportati usando un'identità stabile per evitare duplicati in caso di ripetizione.
Il provider espone anche lo stato del collegamento e, se il deployment ha il client
OAuth Web configurato, **Ricollega Google** permette di rifare il consenso dal sito.

Le scritture agentiche restano distinte da quelle manuali del proprietario e passano
dalle approvazioni previste dal backend. Un errore di rete non autorizza la UI a
ritentare automaticamente una scrittura Google con esito incerto.

## Roadmap ad albero e classificatore locale

La vista Roadmap usa la struttura radici–tronco–rami della snapshot Atlas/qwe e
sovrappone stato/evidenze provenienti da Cora. La struttura non viene generata
automaticamente dai test: modifiche a stelle, rami e gerarchie restano manuali.
Dalla Roadmap il proprietario può avviare collaudi una tantum e richiedere una valutazione locale di fino a otto obiettivi. Architettura mostra i modelli, incluso quello delle priorità. Home mostra fino a cinque voci dell'ultima valutazione salvata. La gerarchia della mappa resta manuale. Dettagli e regole
di aggiornamento sono in [src/tree/README.md](src/tree/README.md).

La pagina principale Architettura non mostra il grafo. Vedi [schede agenti e inferenza desktop](../docs/AGENT-CARDS.md): scelta persistente per ruolo, modelli installati locali o del profilo worker attivo, nessun cambio automatico di profilo o fallback.

## Percorsi aggiunti e grado di verifica

`App.tsx` collega anche Macchine, progetti delle conversazioni, vista Foto e chat con Markdown/GFM, fonti, attività/thinking e preferenza di lunghezza. I suggerimenti iniziali preparano una bozza senza inviarla. Il pannello del modello usa metadati dichiarati dal provider: non attesta qualità o disponibilità futura. Vedi [chat adattiva](../docs/ADAPTIVE_CHAT.md).

Audio include [proposte di note Word](../docs/COMMERCIAL_AUDIO_WORD.md), da rivedere e approvare. Home collega [applicazioni gestite](../docs/MANAGED_APPS.md); il [terminale personale](../docs/personal-terminal.md) richiede servizio/configurazione separati. La presenza dei pulsanti non prova che i relativi servizi siano installati. Foto e collegamenti privati non implementano multiutenza o un backup fotografico verificato.

Lo streaming SSE del backend è distinto dal trasporto worker: il worker remoto restituisce l’inferenza al termine. Una perdita della connessione non autorizza a ritentare una scrittura. Architettura e Macchine permettono controlli manuali. La Roadmap può anche avviare i collaudi registrati per il nodo selezionato.

`npm test` esegue i test Node dichiarati in package.json; `npm run build` esegue TypeScript e Vite. I test di componenti e sorgenti non sono un collaudo end-to-end con Google, Ollama, NAS o Debian. Risultati osservati e limiti nell’[audit](../docs/README_AUDIT_20261025.md).
