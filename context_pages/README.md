# Context Pages prototype

Questa branch server sperimenta contesto e capability **task-scoped** senza disabilitare
il thinking del Supervisor.

Il Supervisor riceve sempre un bootstrap piccolo. Le pagine Markdown in questa
cartella vengono selezionate deterministicamente dal testo dell'utente; nessuna
seconda inferenza LLM viene usata per scegliere il contesto.

Ogni pagina dichiara:
- trigger lessicali;
- capability/tool da esporre al modello;
- poche istruzioni specifiche del dominio.

Un messaggio casuale come `ciao` non carica pagine e non espone tool schema.
Le metriche del run registrano `context_pages`, `selected_tools` e
`selected_tool_count`.

La selezione automatica usa parole intere e frasi normalizzate, senza confronti
per sottostringa. Mail e Audio hanno pagine dedicate. Le continuazioni brevi
(per esempio `sì, procedi`) riprendono il tema precedente dell’utente;
gli estratti degli allegati non attivano strumenti.

La chat permette anche la scelta manuale per il singolo invio: `manual_tools`
assente o `null` usa la selezione automatica; una lista vuota esclude i tool.
Sono selezionabili gli strumenti del Supervisor e le deleghe agli specialisti,
che conservano i propri strumenti. La selezione non esegue un tool da sola e
non concede permessi. Le metriche registrano anche `tool_selection`.


## Owner context on demand

Il contenuto configurato in Gestione Memoria come contesto persistente non viene
più concatenato a ogni prompt. La pagina `owner_context` precarica
il contenuto tramite `owner_context`, senza esporre un tool aggiuntivo: il Supervisor carica quel contenuto solo quando il task
dipende davvero dal profilo/contesto mantenuto dal proprietario o quando l'utente
chiede esplicitamente di usarlo. Anche la memoria semantica non viene più
recuperata automaticamente in ogni turno: la pagina `memory` espone i relativi
tool quando il task lo richiede.
