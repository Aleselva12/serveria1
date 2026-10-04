---
name: create-cora-automation
description: Creare bozze di automazioni compatibili con l'editor Tools, riutilizzando capability esistenti.
---
1. Definisci trigger, input, output, effetti, timeout e casi di errore. Non inventare un esecutore non presente.
2. Consulta programmer_catalog e core/automation_drafts.py per schema e limiti reali.
3. Usa programmer_template("automation"). I nodi sono trigger/tool/condition/output; i cicli non sono supportati.
4. tool_id è l'ID dell'inventario (modulo/percorso.py:nome_funzione), non l'ID capability attore.nome: verifica programmer_validate_automation.
5. Per nodi condizione completa i rami "sì" e "no"; usa tool collegati effettivamente disponibili. Documenta i prerequisiti.
6. Salva automations/<nome>.json con programmer_write_file e valida con programmer_validate_automation.
7. Riferisci warnings e stato bozza. L'importazione nell'editor richiede l'azione esplicita dell'utente; non attiva, pianifica o esegue nulla.

Registra il risultato con programmer_register_component (kind tool o automation), includendo i test. Esegui il profilo contracts e le verifiche pertinenti; prepara programmer_deliver_component. Stati revisionato/integrato/attivo sono riservati all’utente.
