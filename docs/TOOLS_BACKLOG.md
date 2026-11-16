# Promemoria tools e automazioni

Stato del codice: 10 ottobre 2026. Questi promemoria sono visibili anche nel catalogo Tools e nei prossimi passi della Home; non sono notifiche programmate.

| Tool da creare | Funzione | Criterio di completamento |
| --- | --- | --- |
| `server_list_files` | Radici e cartelle autorizzate del server | Listing paginato, rispetto delle radici e dei file riservati; assegnazione esplicita all’agente scelto. |
| `server_read_file` | Lettura e anteprima dei contenuti | Limiti di dimensione, formato e percorsi; nessun accesso fuori radice o a segreti. |
| `server_search_files` | Ricerca nei file del server | Riutilizzare la ricerca esistente con limiti di costo e confini di accesso. |
| `server_manage_files` | Cartelle, copie/spostamenti, cestino e ripristino | Separare le policy per azione; controllo dei conflitti e test di recupero. Nessuna approvazione indiscriminata per ogni operazione. |
| `library_manage_files` | Gestione delle copie IA | Preservare gli originali, distinguere copia da spostamento e proteggere i conflitti. |
| `library_import_file` | Copia dal server alla Libreria IA | Riutilizzare l’importazione esistente; origine preservata e risultato strutturato. |

L’elenco delle intenzioni di integrazione vive in `core/tool_backlog.py`. Le API di upload, sessione, approvazione, monitoraggio, condivisione e controllo runtime restano API dirette: non sono tool agenti mancanti. Il catalogo verifica il tool previsto e il suo collegamento prima di rimuovere l’avviso di integrazione.

## Automazioni grafiche: bozze ed esecuzione manuale

Editor, posizioni, connessioni, configurazioni e salvataggio sono implementati. L’editor elenca le bozze all’apertura, le duplica e le elimina (con controllo di versione), verifica il flusso mentre lo si disegna (`POST /tools/drafts/validate`, senza salvare), genera il modulo dei parametri dallo schema del contratto e mostra effetto e policy dei permessi del tool.

Esecuzione manuale (`core/domain/automation_engine.py`, `core/domain/automation_runs.py`):

- `POST /tools/drafts/{id}/runs` con `{version, mode: dry_run|live, input}` accoda un’esecuzione della versione salvata; `GET /tools/drafts/{id}/runs`, `GET /tools/runs/{run_id}`, `POST /tools/runs/{run_id}/cancel`.
- Ogni nodo tool chiama `execute_capability` del primo contratto del tool: stessi permessi, conferme e registro operazioni degli agenti. Un errore ferma l’esecuzione senza ritentativi.
- Riferimenti `{{input.nome}}` e `{{id_nodo.campo}}`; condizioni `{left, op, right}` con operatori fissi, senza codice libero.
- Prova a vuoto: i tool `read`/`compute` vengono eseguiti, quelli `write`/`delegate` sono mostrati con l’input che riceverebbero ma non eseguiti, come i passaggi che dipendono da loro.
- Conferme: l’esecuzione si mette in attesa senza bloccare la coda; l’approvazione in Attività esegue il tool e l’esecuzione riprende dal nodo successivo leggendo il risultato salvato.
- Un’esecuzione alla volta in un thread dell’API (lock su `CORA_AUTOMATION_RUNS_ROOT/runner.lock`); limite di tempo attivo `CORA_AUTOMATION_RUN_TIMEOUT_SECONDS` (attesa di conferma esclusa). Dopo un riavvio le esecuzioni in corso diventano «interrotte» e non ripartono; quelle in attesa di conferma restano riprendibili.

Restano da implementare: avvio automatico (pianificazione ed eventi), attivazione permanente, annullamento degli effetti già eseguiti, assegnazione agli agenti. Collaudo end-to-end sul server ancora da fare.

## Chat e selezione manuale

Gli allegati testuali, PDF e DOCX sono implementati, con massimo sei file da 5 MB e segnalazione degli estratti limitati. Le registrazioni si caricano nella pagina Audio; il microfono live resta opzionale e rinviato.

Il selettore manuale espone gli strumenti del Supervisor, incluse le deleghe agli specialisti che usano i propri tool. Vale per il singolo invio; `manual_tools: null` sceglie automaticamente, `[]` esclude i tool. Selezionare un tool non lo esegue direttamente e non autorizza nuove azioni. Le policy `auto` non chiedono conferma, `confirm` richiedono l’approvazione esistente, `blocked` restano bloccate.

La selezione automatica usa parole intere e frasi normalizzate: `eventi` non corrisponde a `preventivo`. Mail e Audio hanno pagine dedicate. Le continuazioni brevi riprendono il tema precedente dell’utente; gli estratti degli allegati non decidono quali tool esporre.
