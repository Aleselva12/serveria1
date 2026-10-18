"""Shared paths for server originals and IA working copies."""
import os
import stat
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ORIGINALS_ID = 'ia-originals'

LIBRARY_ERRORS = {
    'LibraryRootInvalid': 'La configurazione del percorso Libreria IA non è valida. Correggi CORA_KNOWLEDGE_ROOT nel backend.',
    'LibraryRootMissing': 'La cartella configurata della Libreria IA non esiste o il suo mount non è disponibile. Verifica il percorso del backend; non è una ricerca senza risultati.',
    'LibraryRootNotDirectory': 'Il percorso configurato della Libreria IA non è una cartella.',
    'LibraryPermissionDenied': 'Il backend non ha accesso alla Libreria IA. Verifica i permessi del servizio sulla cartella.',
    'LibraryStorageUnavailable': 'Lo spazio della Libreria IA non è raggiungibile. Verifica il disco o il mount del backend.',
    'LibraryRootsOverlap': 'Libreria IA e originali devono essere cartelle separate, senza sovrapposizioni.',
    'LibraryDirectoryMissing': 'La sottocartella richiesta non è disponibile nella Libreria IA.',
    'LibraryScanLimit': 'Raggiunto il limite di scansione della Libreria IA. Restringi la ricerca a una sottocartella.',
}


class LibraryAccessError(ValueError):
    def __init__(self, code):
        self.code=code
        super().__init__(LIBRARY_ERRORS[code])


def configured_path(name: str, default: str) -> Path:
    path = Path(os.getenv(name, '').strip() or default).expanduser()
    if not path.is_absolute():
        path = BASE / path
    return path.resolve()


def knowledge_root() -> Path:
    return configured_path('CORA_KNOWLEDGE_ROOT', './knowledge')


def library_workspace_root(*, require_available=True) -> Path:
    """One live resolver for UI and agents. Never invent an explicitly configured mount."""
    try:
        root=knowledge_root()
        originals=configured_path('CORA_LIBRARY_ORIGINALS_ROOT','./data/library_originals')
        if root.is_relative_to(originals) or originals.is_relative_to(root):
            raise LibraryAccessError('LibraryRootsOverlap')
        if not os.getenv('CORA_KNOWLEDGE_ROOT','').strip():
            root.mkdir(parents=True,exist_ok=True)
        if require_available:
            try: info=root.stat()
            except FileNotFoundError as error: raise LibraryAccessError('LibraryRootMissing') from error
            if not stat.S_ISDIR(info.st_mode): raise LibraryAccessError('LibraryRootNotDirectory')
        return root
    except LibraryAccessError: raise
    except PermissionError as error: raise LibraryAccessError('LibraryPermissionDenied') from error
    except OSError as error: raise LibraryAccessError('LibraryStorageUnavailable') from error
    except (ValueError,RuntimeError) as error: raise LibraryAccessError('LibraryRootInvalid') from error


def library_workspace_status():
    """Metadata only; no host paths, filenames or document contents."""
    try:
        root=library_workspace_root()
        with os.scandir(root): pass
        return {'available':True,'code':'ready','message':'Libreria IA disponibile.',
                'configured':bool(os.getenv('CORA_KNOWLEDGE_ROOT','').strip())}
    except LibraryAccessError as error: code=error.code
    except PermissionError: code='LibraryPermissionDenied'
    except OSError: code='LibraryStorageUnavailable'
    return {'available':False,'code':code,'message':LIBRARY_ERRORS[code],
            'configured':bool(os.getenv('CORA_KNOWLEDGE_ROOT','').strip())}


def originals_root() -> Path:
    path = configured_path('CORA_LIBRARY_ORIGINALS_ROOT', './data/library_originals')
    if not os.getenv('CORA_LIBRARY_ORIGINALS_ROOT', '').strip():
        path.mkdir(parents=True, exist_ok=True)
    return path


def original_resource() -> dict:
    return {'id': ORIGINALS_ID, 'label': 'Originali Libreria IA', 'path': str(originals_root()), 'writable': True}
