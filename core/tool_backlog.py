"""Explicit integration intentions, separate from owner-only interface APIs."""
FILE_TOOL_BACKLOG = (
    ("server_list_files", "File server", "Esplorare le radici autorizzate e le cartelle del server; non solo il repository."),
    ("server_read_file", "File server", "Leggere contenuti e anteprime nei percorsi autorizzati del server, con limiti di dimensione."),
    ("server_search_files", "File server", "Ricerca nei file del server attraverso radici e percorsi autorizzati."),
    ("server_manage_files", "File server", "Creare cartelle, copiare o spostare file, cestinare e ripristinare: policy specifiche per azione."),
    ("library_manage_files", "Libreria IA", "Gestire cartelle e copie della libreria, con controllo versione e preservazione degli originali."),
    ("library_import_file", "Libreria IA", "Importare nella libreria una copia di un file del server senza spostare l’originale."),
)


def api_integration(path, method, connected_names):
    """Return required wrappers only for operations deliberately intended for agents.

    Uploads, sessions, sharing, approvals and runtime controls stay direct UI APIs.
    Calendar, memory and specialist operations already have dedicated agent tools.
    """
    server = path.startswith("/api/v1/server/files/")
    library = path.startswith("/api/v1/library/files/")
    suffix = path.rsplit("/", 1)[-1]
    needed = None
    if server:
        if method == "GET" and suffix in {"roots", "children"}: needed = "server_list_files"
        elif method == "GET" and suffix in {"download", "preview"}: needed = "server_read_file"
        elif method == "GET" and suffix == "search": needed = "server_search_files"
        elif suffix in {"folders", "transfer", "trash", "restore"}: needed = "server_manage_files"
    elif library:
        if suffix == "import" and method == "POST": needed = "library_import_file"
        elif suffix in {"folders", "transfer", "trash", "restore"}: needed = "library_manage_files"
    if needed and needed not in connected_names:
        return "integration_needed", needed, "API implementata. Integrazione agenti prevista: manca il tool " + needed + "."
    return "direct", needed, ("API dell’interfaccia; accesso agenti tramite il tool " + needed + "." if needed else
                             "API diretta dell’interfaccia o di servizio. Non richiede assegnazione a un agente; gli eventuali tool usano un contratto separato.")
