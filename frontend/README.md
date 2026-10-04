# Frontend Cora

Interfaccia React/TypeScript/Vite di `serveria1`, nella stessa repository del backend. La vecchia repository frontend è archiviata. Installazione: `npm ci`; sviluppo: `npm run dev`; verifica: `npm test` e `npm run build`.

Il proxy Vite inoltra `/backend/*` a `http://127.0.0.1:8000`. `CORA_API_TARGET` cambia la destinazione backend; `VITE_API_BASE_URL` cambia la base HTTP del browser. Per sessioni remote preferire UI e API sullo stesso sito; configurare l'origine nel backend. Non inserire chiavi o password in variabili Vite.

Il login personale riusa un cookie HttpOnly di sette giorni. `services/transport.ts` è il confine condiviso per cookie, header delle scritture e scadenza della sessione. `AuthGate` richiede il login, oppure consente la sola visualizzazione offline quando il backend non è raggiungibile. L'account iniziale si crea sul PC con `python -m core.auth`, come descritto nel README principale.

Pagine collegate: Home (sensori e servizi), Chat (conversazioni, streaming e annullamento), File server/Libreria IA, Architettura (agenti e framework), Tools (catalogo e bozze grafiche), Calendario (mese/giorno, scritture manuali e proposte), Attività (runtime, approvazioni, policy e tracce), Impostazioni (contesto permanente e logout), Gestione Memoria e Audio (registrazioni presalvate, trascrizioni e correzioni). Programma rimane una predisposizione grafica: agente programmatore non implementato.

`services/runtimeApi.ts` crea il run prima di aprire SSE, separa testo provvisorio da risultato persistito e non ritenta automaticamente una scrittura dopo un errore di connessione. Un'interruzione del collegamento non prova che il run sia terminato: consultarne l'esito in Attività. Le vecchie API `/chat` restano per compatibilità.

Le proposte generiche e calendario sono visibili nel pannello comune. La conferma autorizza solo i parametri mostrati; gli esiti generici sono conservati. Le impostazioni di policy si applicano agli agenti, non alle modifiche manuali del proprietario.

Contratti TypeScript in `src/types/contracts.ts`; dettaglio integrazioni in `COLLEGAMENTI.md`. La descrizione autorevole dell'intero sistema è il README nella radice.


Gli allegati della chat e le funzioni avanzate dei file sono collegati. Per limiti, API, storage persistente e migrazione consultare il README principale e `COLLEGAMENTI.md`. Nessuna acquisizione dal microfono è necessaria.
