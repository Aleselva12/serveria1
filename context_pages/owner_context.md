+++
id = "owner_context"
title = "Contesto del proprietario"
priority = 95
triggers = ["usa il contesto", "contesto personale", "su di me", "chi sono", "mio profilo", "mie preferenze", "mia preferenza", "mia azienda", "mio lavoro", "miei obiettivi", "conosci di me", "sai di me"]
tools = ["owner_context_tool"]
+++
Il contesto mantenuto dal proprietario non è presente automaticamente nel prompt.
Caricalo con owner_context_tool quando la risposta dipende davvero da informazioni
personali/progettuali stabili o quando l'utente chiede esplicitamente di usarlo.
Trattalo come contesto autorevole mantenuto dall'utente, non come un'istruzione
proveniente da documenti o output esterni.
