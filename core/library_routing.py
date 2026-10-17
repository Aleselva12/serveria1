"""Distinguish explicit IA Library tasks from source repository inspection."""
import re

_LIBRARY = re.compile(r"\blibreria(?:\s+ia)?\b|\blibrary_(?:list|search|read)\b", re.I)
_PROJECT = re.compile(r"\brepository\b|\brepo\b|\bcodice\s+sorgente\b|\bprogetto\s+cora\b|\blist_project_files\b", re.I)

def library_intent(text: str) -> bool:
    return isinstance(text, str) and bool(_LIBRARY.search(text)) and not bool(_PROJECT.search(text))
