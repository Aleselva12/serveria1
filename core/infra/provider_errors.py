"""Fixed provider diagnostics: never store exception text, URLs or response bodies."""
MESSAGES = {
    'timeout': 'Tempo massimo di risposta del modello superato.',
    'connection': 'Connessione al servizio Ollama non riuscita.',
    'missing': 'Risorsa o modello Ollama non trovato (HTTP 404). Verificare modello ed endpoint.',
    'auth': 'Accesso al servizio del modello rifiutato (HTTP 401/403).',
    'busy': 'Servizio del modello temporaneamente occupato (HTTP 429/503).',
    'memory': 'Ollama segnala memoria insufficiente per caricare o eseguire il modello.',
    'tools': 'Il modello Ollama selezionato non supporta i tool richiesti.',
    'request': 'Ollama ha rifiutato la richiesta. Verificare formato e compatibilità del modello.',
    'server': 'Errore interno del servizio Ollama durante l’inferenza.',
    'response': 'Risposta di errore da Ollama; dettaglio testuale omesso per riservatezza.',
}


def safe_detail(value):
    return value if isinstance(value, str) and value in MESSAGES.values() else None


def provider_detail(error):
    import httpx
    from ollama import ResponseError
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return MESSAGES['timeout']
    if isinstance(error, (ConnectionError, httpx.ConnectError)):
        return MESSAGES['connection']
    if not isinstance(error, ResponseError):
        return None
    # Classify the provider body locally, emitting only fixed messages.
    text = str(getattr(error, 'error', '')).casefold()
    if 'out of memory' in text or 'requires more system memory' in text:
        return MESSAGES['memory']
    if 'does not support tools' in text:
        return MESSAGES['tools']
    status = getattr(error, 'status_code', None)
    if status == 404: return MESSAGES['missing']
    if status in (401, 403): return MESSAGES['auth']
    if status in (429, 503): return MESSAGES['busy']
    if isinstance(status, int) and 400 <= status < 500: return MESSAGES['request']
    if isinstance(status, int) and 500 <= status < 600: return MESSAGES['server']
    return MESSAGES['response']
