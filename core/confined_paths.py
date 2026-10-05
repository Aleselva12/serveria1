"""Contain filesystem paths before any IO, including server-side metadata paths.

The configured root is trusted. Callers must still validate public path syntax and
reserved names. Symlink checks do not lock out concurrent external NAS writers.
"""
import os
from pathlib import Path
from fastapi import HTTPException


def confined_path(root: Path, candidate: Path, *, allow_leaf_link: bool = False) -> Path:
    base = os.path.realpath(root)
    prefix = base.rstrip(os.sep) + os.sep
    lexical = os.path.abspath(candidate)
    if lexical == base:
        return Path(base)
    if not lexical.startswith(prefix):
        raise HTTPException(403, 'Percorso esterno alla risorsa.')
    # For a directory listing only, inspect the link itself, never its target.
    if allow_leaf_link:
        normalized = os.path.join(os.path.realpath(os.path.dirname(lexical)), os.path.basename(lexical))
    else:
        normalized = os.path.realpath(lexical)
    if normalized == base:
        return Path(base)
    if not normalized.startswith(prefix):
        raise HTTPException(403, 'Percorso esterno alla risorsa.')
    # Reject even links pointing inside the root; otherwise a later link change
    # would change the object selected by the request.
    cursor = Path(base)
    segments = Path(lexical).relative_to(base).parts
    for index, segment in enumerate(segments):
        cursor = cursor / segment
        if cursor.is_symlink() and not (allow_leaf_link and index == len(segments) - 1):
            raise HTTPException(403, 'I collegamenti simbolici non sono navigabili.')
    return Path(normalized)
