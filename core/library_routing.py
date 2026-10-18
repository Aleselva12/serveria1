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
    from tools import library_list
    from core.library_preflight import _invoke, _unavailable
    data,error = _invoke(library_list,{"directory": ".", "recursive": True},action='elenco',for_model=False)
    if error: return error
    rows = data.get("documents")
    if not isinstance(rows,list) or any(not isinstance(row,dict) or not isinstance(row.get('path'),str) for row in rows):
        return _unavailable(action='elenco',for_model=False)
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
