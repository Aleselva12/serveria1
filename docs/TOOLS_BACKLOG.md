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

## Automazioni grafiche: solo bozze

Editor, posizioni, connessioni, configurazioni e salvataggio sono implementati. Restano da implementare: esecutore, mapping dei dati fra nodi, condizioni eseguibili, pianificazione e assegnazione agli agenti. Nessuna bozza viene attivata o eseguita dalla selezione nella UI.

## Chat e selezione manuale

Gli allegati testuali, PDF e DOCX sono implementati, con massimo sei file da 5 MB e segnalazione degli estratti limitati. Le registrazioni si caricano nella pagina Audio; il microfono live resta opzionale e rinviato.

Il selettore manuale espone gli strumenti del Supervisor, incluse le deleghe agli specialisti che usano i propri tool. Vale per il singolo invio; `manual_tools: null` sceglie automaticamente, `[]` esclude i tool. Selezionare un tool non lo esegue direttamente e non autorizza nuove azioni. Le policy `auto` non chiedono conferma, `confirm` richiedono l’approvazione esistente, `blocked` restano bloccate.

La selezione automatica usa parole intere e frasi normalizzate: `eventi` non corrisponde a `preventivo`. Mail e Audio hanno pagine dedicate. Le continuazioni brevi riprendono il tema precedente dell’utente; gli estratti degli allegati non decidono quali tool esporre.
