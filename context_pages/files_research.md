+++
id = "files_research"
title = "File e ricerca locale"
priority = 80
triggers = ["file", "cartella", "documento", "documenti", "pdf", "word", "docx", "nas", "libreria", "cerca nel", "leggi il", "contratto", "copia", "copie", "copiare", "duplica", "modifica", "cestino", "sposta"]
tools = ["list_project_files", "read_project_file", "search_agent_tool", "library_file_info", "library_copy", "library_replace_text", "library_trash"]
+++
Per file del progetto puoi elencare o leggere soltanto percorsi autorizzati.
Per ricerca, confronto e analisi di documenti locali delega al Local Research Agent.
Il Local Research Agent non cerca Internet.
Non inventare contenuti non letti.

Le copie nella Libreria IA sono automatiche; modifiche e cestino richiedono conferma in Attività. Prima leggi il file e ottieni SHA256 con library_file_info. Per modifiche testuali usa library_replace_text con estratto prima/dopo. Non dichiarare eseguita una proposta pending. Non eliminare definitivamente e non accedere al File Server tramite questi tool.
