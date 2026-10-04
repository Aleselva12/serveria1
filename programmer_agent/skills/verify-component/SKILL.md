---
name: verify-component
description: Verificare codice generato con sintassi e test isolati, distinguendo i risultati effettivi dalle verifiche mancanti.
---
1. Consulta programmer_diff e seleziona controlli che provino il comportamento richiesto, inclusi gli errori rilevanti.
2. programmer_check("syntax") analizza Python e JSON senza eseguire il codice: non prova import, tipi o comportamento.
3. programmer_check("python_tests") esegue unittest discover in Docker senza rete, credenziali o dati del server. Non esiste fallback host.
4. Usa dati sintetici. Non collegare test a PostgreSQL, Gmail o cartelle personali; il container non ha accesso ai servizi.
5. Se manca Docker o l'immagine, riferisci "test non eseguiti". Se falliscono, correggi e ripeti solo i controlli pertinenti.
6. programmer_check con profilo contracts ispeziona adapter e bozze senza importare Python. typescript e frontend_build usano solo il container Node preparato, senza installare dipendenze.
7. Registra il componente con file e test, dipendenze e istruzioni di integrazione. Prepara la consegna con programmer_deliver_component; segnala verifiche mancanti.
8. Riporta profilo, esito e limiti: nessuna affermazione di validazione frontend basata sul controllo Python.
