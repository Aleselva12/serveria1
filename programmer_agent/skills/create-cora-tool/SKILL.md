---
name: create-cora-tool
description: Creare un tool Cora con contratto, permessi e verifiche, mantenendolo come bozza nel workspace.
---
1. Chiarisci input, output ed effetti della richiesta. Consulta programmer_catalog per riutilizzare capacità esistenti.
2. Leggi un tool vicino al caso d'uso e core/governance.py, core/permissions.py nel workspace.
3. Usa programmer_template("tool"). Separa logica pura dall'adapter agent_tool; mantieni input/output tipizzati.
4. Scegli ID stabile, azioni esplicite, effect read/compute/write/delegate e retry safe solo per letture/calcoli ripetibili.
5. Scrivi in generated_tools/<nome>.py e aggiungi __init__.py. Non modificare il codice attivo.
6. Scrivi test con dati sintetici in tests/test_generated_<nome>.py. Usa programmer_check("syntax"), poi python_tests se Docker è pronto.
7. Leggi programmer_diff. Riferisci verifiche e integrazioni necessarie: regole permessi, bind_capabilities, catalogo.
Un file scritto non è una capability attiva. Non importare o registrare dinamicamente codice generato nel server.
