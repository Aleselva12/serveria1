# Desktop Windows, aggiornamenti e risposte del Programmatore

## Diagnosi del run 92805733 (18 ottobre 2026)

Il PDF e la lettura del PostgreSQL locale concordano: `programmer_read_skill`,
`programmer_list_files` e `programmer_search_code` hanno terminato correttamente.
La chiamata successiva al modello termina, poi il nodo `call_llm` genera un
`ValueError`. Non risultano scritture o automazioni create da quel run.

La diagnostica precedente elimina il payload `programmer.context_call` e conserva
solo il tipo dell'errore. Non è possibile stabilire retroattivamente se quella
risposta fosse vuota oppure contenesse tool malformati. Entrambi i controlli erano
presenti nel nodo. Non si attribuisce il problema al tool di ricerca riuscito.

Ora ogni risposta viene validata, considerando anche whitespace e blocchi di solo
ragionamento. Una risposta inutilizzabile viene scartata e si tenta una sola
correzione del modello mantenendo i risultati precedenti. Nessun tool viene
rieseguito dal recupero. Timeout, cancellazioni ed effetti incerti non sono
ritentati. Un secondo fallimento genera `ProgrammerResponseError`; gli eventi
`programmer.response_validation` conservano motivo, tentativo e conteggi, senza
prompt, argomenti o testo privato.

La risposta finale elenca i risultati tool della richiesta corrente, separandoli
dal testo del modello e dalle verifiche effettivamente registrate sul digest del
workspace. Una bozza o una dichiarazione testuale non attiva un'automazione.

## Accesso

`AVVIO.cmd` / `AVVIO.ps1` imposta `CORA_AUTH_MODE=desktop` nel processo locale e
mantiene API e Vite su loopback. Il proprietario esistente viene mantenuto per audit
e approvazioni; alla prima installazione viene creata un'identità con password
casuale senza chiedere il vecchio login. I vecchi cookie non sono necessari.

Il middleware richiede peer loopback, Host locale letterale, origine locale quando
presente e assenza di header proxy. Le scritture richiedono ancora `X-Cora-Client`
e origine consentita. Il desktop non è una modalità per esporre l'app in LAN o
tramite proxy; sul server usare Tailscale con identità e segreto proxy configurati,
oppure conservare la modalità password. Un cambio di modalità richiede il riavvio
del backend. Il launcher non considera il vecchio backend password come già pronto.

## Aggiorna Cora

Il pulsante apre un pannello e consulta un endpoint protetto; non usa più un
indirizzo Debian fisso.

* **Windows:** una richiesta esplicita prepara un candidato dal commit `main`
  risolto tramite GitHub. Download e archivio sono limitati; traversal, link,
  duplicati, nomi Windows riservati e stato privato vengono rifiutati. I sorgenti
  sono estratti in una cartella sorella separata, mai sopra la copia corrente.
  Si eseguono la suite Windows definita in `WINDOWS_TESTS`, tutti i test frontend
  e la build. L'ambiente di test rimuove la configurazione Cora/PostgreSQL/Ollama
  del servizio; usa l'interprete corrente e richiede npm. I log si trovano nei
  file `update-checks.log` del candidato e della sua cartella frontend.
* **Debian:** impostare `CORA_UPDATE_URL` all'URL HTTPS della pagina host già
  installata. Configurazione assente o non valida viene mostrata esplicitamente.
  L'app non installa il bridge né modifica Docker o systemd. Configurazione,
  backup, applicazione e recupero restano descritti in `updater/README.md`.

`ready` significa solo candidato verificato. Prima dell'attivazione desktop fare
backup di PostgreSQL e `data`, arrestare i servizi attuali e avviare `ATTIVA.ps1`
dal candidato. Lo script rifiuta porte 8000/5173 ancora in ascolto, copia `.env`,
crea una junction verso i dati originali e avvia il launcher. La copia precedente
resta disponibile. Un ritorno al vecchio codice richiede un database compatibile:
la junction non è un backup né un rollback delle migrazioni. Nessuna attivazione
avviene automaticamente dal worker HTTP. Se il backend si arresta durante la
preparazione il job in memoria si perde: il candidato incompleto non è attivabile
dal pannello e va riesaminato o preparato di nuovo.

## Verifiche e limiti

La suite server completa è eseguita dalla CI Linux con PostgreSQL di test; la CI
Windows usa la stessa suite `WINDOWS_TESTS` dell'aggiornamento e la build frontend.
La suite backend completa su questo PC presenta fallimenti già riproducibili sul
commit base (permessi/symlink POSIX, nomi file lunghi, percorsi Compose, mock
monitoraggio). Non sono conteggiati come successi. Non si prova l'updater Debian
di produzione applicando un rilascio al server dell'utente.
