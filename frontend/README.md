# Frontend Cora

Interfaccia React/TypeScript/Vite di `serveria1`, nella stessa repository del backend. La vecchia repository frontend Ã¨ archiviata. Installazione: `npm ci`; sviluppo: `npm run dev`; verifica: `npm test` e `npm run build`.

Il proxy Vite inoltra `/backend/*` a `http://127.0.0.1:8000`. `CORA_API_TARGET` cambia la destinazione backend; `VITE_API_BASE_URL` cambia la base HTTP del browser. Per sessioni remote preferire UI e API sullo stesso sito; configurare l'origine nel backend. Non inserire chiavi o password in variabili Vite.

In modalità password il login personale riusa un cookie HttpOnly di sette giorni; desktop e Tailscale hanno percorsi distinti, dichiarati da `/auth/status`. `services/transport.ts` Ã¨ il confine condiviso per cookie, header delle scritture e scadenza della sessione. `AuthGate` richiede il login, oppure consente la sola visualizzazione offline quando il backend non Ã¨ raggiungibile. L'account iniziale si crea sul PC con `python -m core.auth`, come descritto nel README principale.

Pagine collegate: Home (sensori e servizi), Chat (conversazioni, streaming e annullamento), File server/Libreria IA, Architettura (schede agenti, modelli per agente e programmi separati), Tools (catalogo e bozze grafiche), Calendario (mese/giorno, scritture manuali e proposte), AttivitÃ  (runtime, approvazioni, policy e tracce), Impostazioni (contesto permanente e logout), Gestione Memoria e Audio (registrazioni presalvate, trascrizioni e correzioni). Programma Ã¨ collegato al Programmatore con workspace isolati e Copilot; non applica automaticamente le modifiche al codice attivo.

`services/runtimeApi.ts` crea il run prima di aprire SSE, separa testo provvisorio da risultato persistito e non ritenta automaticamente una scrittura dopo un errore di connessione. Un'interruzione del collegamento non prova che il run sia terminato: consultarne l'esito in AttivitÃ . Le vecchie API `/chat` restano per compatibilitÃ .

Le proposte generiche e calendario sono visibili nel pannello comune. La conferma autorizza solo i parametri mostrati; gli esiti generici sono conservati. Le impostazioni di policy si applicano agli agenti, non alle modifiche manuali del proprietario.

Contratti TypeScript in `src/types/contracts.ts`; dettaglio integrazioni in `COLLEGAMENTI.md`. La descrizione autorevole dell'intero sistema Ã¨ il README nella radice.


Gli allegati della chat e le funzioni avanzate dei file sono collegati. Per limiti, API, storage persistente e migrazione consultare il README principale e `COLLEGAMENTI.md`. Nessuna acquisizione dal microfono Ã¨ necessaria.

La pagina principale Architettura non mostra il grafo. Vedi [schede agenti e inferenza desktop](../docs/AGENT-CARDS.md): scelta persistente per ruolo, modelli installati locali o del profilo worker attivo, nessun cambio automatico di profilo o fallback.

## Percorsi aggiunti e grado di verifica

`App.tsx` collega anche Macchine, progetti delle conversazioni, vista Foto e chat con Markdown/GFM, fonti, attività/thinking e preferenza di lunghezza. I suggerimenti iniziali preparano una bozza senza inviarla. Il pannello del modello usa metadati dichiarati dal provider: non attesta qualità o disponibilità futura. Vedi [chat adattiva](../docs/ADAPTIVE_CHAT.md).

Audio include [proposte di note Word](../docs/COMMERCIAL_AUDIO_WORD.md), da rivedere e approvare. Home collega [applicazioni gestite](../docs/MANAGED_APPS.md); il [terminale personale](../docs/personal-terminal.md) richiede servizio/configurazione separati. La presenza dei pulsanti non prova che i relativi servizi siano installati. Foto e collegamenti privati non implementano multiutenza o un backup fotografico verificato.

Lo streaming SSE del backend è distinto dal trasporto worker: il worker remoto restituisce l’inferenza al termine. Una perdita della connessione non autorizza a ritentare una scrittura. I controlli di modello/machine restano manuali in Architettura/Macchine.

`npm test` esegue i test Node dichiarati in package.json; `npm run build` esegue TypeScript e Vite. I test di componenti e sorgenti non sono un collaudo end-to-end con Google, Ollama, NAS o Debian. Risultati osservati e limiti nell’[audit](../docs/README_AUDIT_20261025.md).
