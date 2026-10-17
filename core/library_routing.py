"""Distinguish explicit IA Library tasks from source repository inspection."""
import re

_LIBRARY = re.compile(r"\blibreria(?:\s+ia)?\b|\blibrary_(?:list|search|read)\b", re.I)
_PROJECT = re.compile(r"\brepository\b|\brepo\b|\bcodice\s+sorgente\b|\bprogetto\s+cora\b|\blist_project_files\b", re.I)

def library_intent(text: str) -> bool:
    return isinstance(text, str) and bool(_LIBRARY.search(text)) and not bool(_PROJECT.search(text))

def list_requested(text: str) -> bool:
    if not library_intent(text):
        return False
    return bool(re.search(r"\b(?:elenca|elenco|lista|list|mostra|quali|vedere|vedi)\b", text, re.I)
                or re.search(r"\blibrary_list\b", text, re.I))

def list_documents_direct() -> str:
    """No Ollama required. Reuse governed Library API, preserving permissions."""
    import json
    from tools import library_list
    response = library_list.invoke({"directory": ".", "recursive": True})
    data = json.loads(response)
    if data.get("status") == "error":
        return "Impossibile consultare la Libreria IA: " + str(data.get("error", "errore"))[:250]
    rows = data.get("documents", [])
    if not rows:
        return "Non risultano documenti leggibili nella Libreria IA."
    result = ["Documenti trovati nella Libreria IA:"]
    for row in rows:
        path = str(row.get("path", ""))
        result.append("- " + path + " · formato " + str(row.get("type", "")) +
                      " · " + str(row.get("size_bytes", "?")) + " byte")
    result.append("Percorsi relativi alla Libreria IA.")
    if len(rows) >= 200:
        result.append("Elenco limitato a 200 risultati: restringi la ricerca per vedere gli altri.")
    return "\n".join(result)
