"""IA working copies. Import/upload always preserve a separate server original."""
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from core.confined_paths import confined_path
from core.file_paths import ORIGINALS_ID, library_workspace_root, LibraryAccessError
from core.server_files import (exists, make_router, node, operation, parts,
                               resolve, root_for, upload_to, vacant)

LIBRARY_ID = 'library'


def library_roots():
    try: library = library_workspace_root(require_available=False)
    except LibraryAccessError as error: raise HTTPException(503,str(error)) from error
    return [{'id': LIBRARY_ID, 'label': 'Libreria IA', 'path': str(library), 'writable': True}]


router = make_router('/api/v1/library/files', 'Libreria IA', library_roots, allow_upload=False)


def library_base():
    _, base = root_for(LIBRARY_ID, root_provider=library_roots)
    return base


def copy_document(source: Path, destination: Path, library: Path):
    destination = confined_path(library, destination)
    exists(source)
    if not source.is_file():
        raise HTTPException(400, 'Seleziona un file normale da copiare.')
    if source.resolve().is_relative_to(library):
        raise HTTPException(400, 'Il file selezionato è già nella Libreria IA.')
    vacant(destination)
    staging = confined_path(library, library / '.cora-staging')
    if staging.is_symlink():
        raise HTTPException(403, 'Area temporanea non valida.')
    staging.mkdir(exist_ok=True)
    fd, name = tempfile.mkstemp(dir=staging)
    temporary = Path(name)
    try:
        # A byte copy, never a hard link to the server original.
        with os.fdopen(fd, 'wb') as writer, source.open('rb') as reader:
            shutil.copyfileobj(reader, writer)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            raise HTTPException(409, 'Esiste già una copia con questo nome.') from None
    finally:
        temporary.unlink(missing_ok=True)
    return node(library, destination, True)


class ImportFile(BaseModel):
    source_root_id: str
    source_path: str = Field(min_length=1)
    destination: str = Field(min_length=1)


@router.post('/import', status_code=201)
def import_file(body: ImportFile):
    with operation():
        library = library_base()
        _, base = root_for(body.source_root_id)
        source = resolve(base, body.source_path)
        destination = resolve(library, body.destination)
        result = copy_document(source, destination, library)
        return {'copy': result, 'original': {'rootId': body.source_root_id, 'path': body.source_path}}


@router.post('/upload', status_code=201)
def upload_copy(path: str = Form(''), file: UploadFile = File(...)):
    with operation():
        library = library_base()
        filename = file.filename or ''
        if len(parts(filename)) != 1:
            raise HTTPException(400, 'Nome file non valido.')
        destination = resolve(library, '/'.join(filter(None, [path, filename])))
        vacant(destination)
        root, originals = root_for(ORIGINALS_ID, write=True)
        # Unique folder allows repeated uploads without ever replacing an original.
        folder = uuid.uuid4().hex
        (originals / folder).mkdir()
        try:
            original = upload_to(root, originals, folder, file)
        except Exception:
            try:
                (originals / folder).rmdir()
            except OSError:
                # A published original may already exist: never delete it, nor
                # conceal the exception raised after its publication.
                pass
            raise
        try:
            result = copy_document(resolve(originals, original['path']), destination, library)
        except Exception as error:
            # Once saved, keep the original even if publishing the library copy fails.
            status = error.status_code if isinstance(error, HTTPException) else 503
            raise HTTPException(status, 'Copia IA non creata; originale conservato in Originali Libreria IA/' + original['path']) from error
        return {'copy': result, 'original': {'rootId': ORIGINALS_ID, 'path': original['path']}}

class MonitorFolder(BaseModel):
    folder: str = Field(min_length=1)
    enabled: bool

@router.get('/monitor')
def monitor_status():
    from core.library_monitor import status
    return status()

@router.put('/monitor/folder')
def monitor_folder(body: MonitorFolder):
    from core.library_monitor import set_folder
    with operation():
        try:
            return set_folder(body.folder, body.enabled)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error

@router.post('/monitor/scan')
def monitor_scan():
    from core.library_monitor import scan_once, status
    with operation():
        if not scan_once():
            raise HTTPException(503, 'Scansione non completata; registro precedente conservato.')
        return status()
