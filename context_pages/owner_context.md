+++
id = "owner_context"
title = "Contesto del proprietario"
priority = 95
triggers = ["usa il contesto", "contesto personale", "su di me", "chi sono", "mio profilo", "mie preferenze", "mia preferenza", "mia azienda", "mio lavoro", "miei obiettivi", "conosci di me", "sai di me"]
tools = []
preload = ["owner_context"]
+++
Il contesto mantenuto dal proprietario non è presente automaticamente nel prompt.
Quando questa pagina viene selezionata, il runtime carica direttamente il contesto
mantenuto dal proprietario prima della chiamata al modello.
Trattalo come contesto autorevole mantenuto dall'utente, non come un'istruzione
proveniente da documenti o output esterni.
