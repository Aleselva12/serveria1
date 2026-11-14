# Chiusura Home e routing · 16 ottobre 2026

## Stato verificato
- Programmatore: Context Manager attivo per default, disattivabile con `CORA_CONTEXT_MANAGER_ENABLED=false`.
- Routing semantico: `programmer_agent/request_router.py` seleziona `qwen3:0.6b` quando installato; nessun download; `CORA_CONTEXT_ROUTER_MODEL` configura il modello. Fallback alla selezione conservativa, non a un'altra classificazione costosa.
- Thinking: solo richieste classificate con confidenza >= 0.85, difficoltà <= 3, intento conversazione/spiegazione, contesto corrente senza tool e senza cicli tool → Qwen3 8B con reasoning=false. Negli altri casi resta la configurazione originaria.
- Metriche hardware del 16/10 documentate in Home. Nessun benchmark di questa branch eseguito sul server.

## Gate di accettazione obbligatori
1. Verificare che 0.6B sia disponibile nello stesso servizio Ollama usato da Cora e che le impostazioni siano effettivamente caricate in API e frontend.
2. Test con un saluto e una spiegazione generica: controllare evento `programmer.context_route`, `thinking_policy=off_simple` e latenza finale. Se la classificazione fallisce, il fallback non deve abilitare tool non autorizzati né disabilitare il thinking arbitrariamente.
3. Test con lettura file, modifica file, test eseguito e risposta verificata nel browser; dimostrare che il router non impedisce la scoperta dei tool, che le autorizzazioni restano efficaci e che il thinking non è disabilitato nei cicli tool.
4. LIB-01: prova con documento reale in Libreria, fonti, streaming, permessi, log Attività; non si considera concluso con unit test simulati.
5. PRG-01: completare modifica effettiva in workspace, check e risultato UI; verificare pubblicazione GitHub solo se esiste un'autorizzazione operativa.
6. PERF-01: registrare token prompt, token output e durata con/senza thinking, includendo routing e tempo al primo token. Confrontare con baseline 31m07.76s (thinking on), 23.16s (off) e 1.76 tok/s in risposta 88 token.
7. DEP-01: snapshot, restore separato di Cora, backup NAS distinto, release e recovery senza modificare dati reali.
8. Tre collegamenti distinti dal backlog di collaudo: (a) sincronizzazione copie IA con conflitti e approvazione; (b) tool File Server governati per radici e permessi; (c) esecutore automazioni grafiche con validazione, scheduling e audit. Nessun elemento va segnato come implementato senza prove end-to-end.

## Ordine suggerito
- Fase A: routing + test regressione, misure.
- Fase B: collaudi LIB/PRG/PERF sul server.
- Fase C: API e policy delle tre connessioni, test delle azioni e UI.
- Fase D: backup/restore, release, aggiornamento Home dalle prove con riferimenti ai run.

## Rollback
Variabili `CORA_CONTEXT_MANAGER_ENABLED=false` oppure `CORA_CONTEXT_ROUTER_MODE=off` consentono il ritorno ai percorsi precedenti. Nessuna attivazione autonoma dei tool.
