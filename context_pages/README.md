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

È un prototipo. In futuro la selezione potrà combinare segnali UI, metadata,
embedding delle descrizioni e pagine create in bozza/validate/publish.


## Owner context on demand

Il contenuto configurato in Gestione Memoria come contesto persistente non viene
più concatenato a ogni prompt. La pagina `owner_context` espone
`owner_context_tool`: il Supervisor carica quel contenuto solo quando il task
dipende davvero dal profilo/contesto mantenuto dal proprietario o quando l'utente
chiede esplicitamente di usarlo. Anche la memoria semantica non viene più
recuperata automaticamente in ogni turno: la pagina `memory` espone i relativi
tool quando il task lo richiede.
