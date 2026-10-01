"""Shared paths for server originals and IA working copies."""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ORIGINALS_ID = 'ia-originals'


def configured_path(name: str, default: str) -> Path:
    path = Path(os.getenv(name, '').strip() or default).expanduser()
    if not path.is_absolute():
        path = BASE / path
    return path.resolve()


def knowledge_root() -> Path:
    return configured_path('CORA_KNOWLEDGE_ROOT', './knowledge')


def originals_root() -> Path:
    path = configured_path('CORA_LIBRARY_ORIGINALS_ROOT', './data/library_originals')
    if not os.getenv('CORA_LIBRARY_ORIGINALS_ROOT', '').strip():
        path.mkdir(parents=True, exist_ok=True)
    return path


def original_resource() -> dict:
    return {'id': ORIGINALS_ID, 'label': 'Originali Libreria IA', 'path': str(originals_root()), 'writable': True}
