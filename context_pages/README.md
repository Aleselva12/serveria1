# Pagine di contesto del Supervisor

Il percorso integrato in `graph.py` seleziona contesto e capability per richiesta.
Il thinking dipende dai metadati e dal default del provider, non viene garantito da queste pagine.

Il Supervisor riceve sempre un bootstrap piccolo. Le pagine Markdown in questa
cartella vengono selezionate deterministicamente dal testo dell'utente; nessuna
seconda inferenza LLM viene usata per scegliere il contesto.

Ogni pagina eseguibile usa frontmatter TOML delimitato da `+++` e dichiara:
- trigger lessicali;
- capability/tool da esporre al modello;
- poche istruzioni specifiche del dominio.

Un messaggio casuale come `ciao` non carica pagine e non espone tool schema.
Le metriche del run registrano `context_pages`, `selected_tools` e
`selected_tool_count`.

La selezione automatica usa parole intere e frasi normalizzate, senza confronti
per sottostringa. Mail e Audio hanno pagine dedicate. Le continuazioni brevi
(per esempio `sÃ¬, procedi`) riprendono il tema precedente dellâ€™utente;
gli estratti degli allegati non attivano strumenti.

La chat permette anche la scelta manuale per il singolo invio: `manual_tools`
assente o `null` usa la selezione automatica; una lista vuota esclude i tool.
Sono selezionabili gli strumenti del Supervisor e le deleghe agli specialisti,
che conservano i propri strumenti. La selezione non esegue un tool da sola e
non concede permessi. Le metriche registrano anche `tool_selection`.


## Owner context on demand

Il contenuto configurato in Gestione Memoria come contesto persistente non viene
piÃ¹ concatenato a ogni prompt. La pagina `owner_context` precarica
il contenuto tramite `owner_context`, senza esporre un tool aggiuntivo: il Supervisor carica quel contenuto solo quando il task
dipende davvero dal profilo/contesto mantenuto dal proprietario o quando l'utente
chiede esplicitamente di usarlo. Anche la memoria semantica non viene piÃ¹
recuperata automaticamente in ogni turno: la pagina `memory` espone i relativi
tool quando il task lo richiede.

## Collegamento e limiti

`core/context_pages.py` carica soltanto Markdown con frontmatter, esclude questo README e seleziona al massimo tre pagine per punteggio lessicale/priorità. `graph.py` aggiunge le istruzioni comuni e gli eventuali dati precaricati. Le metriche dichiarano selezione e precaricamento, non una lettura completa della memoria.

In selezione automatica, `core/library_routing.py` può aggiungere `library_list/search/read` e rimuovere gli strumenti di esplorazione repository per richieste sulla sola Libreria IA. La lista manuale prevale e viene validata in `core/chat_tools.py`; gli specialisti mantengono i propri strumenti governati. Il budget finito e i metadati del modello possono ancora impedire una richiesta: selezione non significa esecuzione riuscita.

Prove nel repository: `tests/test_context_pages.py`, `test_owner_context_pages.py`, `test_chat_tools.py`, `test_library_routing.py`. [Audit del 25 ottobre](../docs/README_AUDIT_20261025.md): collegamento statico verificato, nessun collaudo di inferenza sul Debian reale.
