"""IA working copies. Import/upload always preserve a separate server original."""
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from core.file_paths import ORIGINALS_ID, knowledge_root, originals_root
from core.server_files import (exists, make_router, node, operation, parts,
                               resolve, root_for, upload_to, vacant)

LIBRARY_ID = 'library'


def library_roots():
    library = knowledge_root()
    originals = originals_root()
    if library.is_relative_to(originals) or originals.is_relative_to(library):
        raise HTTPException(503, 'Libreria IA e originali devono essere cartelle separate.')
    if not os.getenv('CORA_KNOWLEDGE_ROOT', '').strip():
        library.mkdir(parents=True, exist_ok=True)
    return [{'id': LIBRARY_ID, 'label': 'Libreria IA', 'path': str(library), 'writable': True}]


router = make_router('/api/v1/library/files', 'Libreria IA', library_roots, allow_upload=False)


def library_base():
    _, base = root_for(LIBRARY_ID, root_provider=library_roots)
    return base


def copy_document(source: Path, destination: Path, library: Path):
    exists(source)
    if not source.is_file():
        raise HTTPException(400, 'Seleziona un file normale da copiare.')
    if source.resolve().is_relative_to(library):
        raise HTTPException(400, 'Il file selezionato è già nella Libreria IA.')
    vacant(destination)
    staging = library / '.cora-staging'
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
            (originals / folder).rmdir()
            raise
        try:
            result = copy_document(originals / original['path'], destination, library)
        except Exception as error:
            # Once saved, keep the original even if publishing the library copy fails.
            status = error.status_code if isinstance(error, HTTPException) else 503
            raise HTTPException(status, 'Copia IA non creata; originale conservato in Originali Libreria IA/' + original['path']) from error
        return {'copy': result, 'original': {'rootId': ORIGINALS_ID, 'path': original['path']}}
