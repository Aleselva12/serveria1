+++
id = "programming"
title = "Programmazione"
priority = 90
triggers = ["codice", "programma", "programmazione", "repository", "repo", "github", "branch", "commit", "bug", "funzione", "classe", "programmer", "programmatore"]
tools = ["programmer_agent_tool", "list_project_files", "read_project_file"]
+++
Il Programmer Agent lavora su workspace separati e non modifica direttamente il codice Cora attivo.
Per delegargli lavoro serve un workspace_id reale già creato/selezionato nella pagina Programma.
Non inventare workspace ID e non dichiarare pubblicata o applicata una modifica senza conferma del relativo flusso.
Per orientarsi nel progetto, usa README.md come mappa breve e docs/AGENT_CONTEXT.md
per scegliere uno o due documenti specialistici; audit datati e validation report
sono storico, non stato corrente. Conferma nel codice i contratti che devi modificare.
