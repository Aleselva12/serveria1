"""Agent writes restricted to IA working copies, with version-bound approvals."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid
from datetime import datetime, timezone

from core.governance import agent_tool
from core.server_files import operation, trash_area
from core.confined_paths import confined_path
from core.runtime_context import ensure_runtime_active


def source_file(relative_path):
    ensure_runtime_active()
    from search_agent import search_tools as research
    path = research._safe_path(relative_path)
    if not path.is_file():
        raise ValueError('Seleziona un file normale nella Libreria IA.')
    if path.stat().st_size > research.MAX_FILE_BYTES:
        raise ValueError('File oltre il limite di dimensione configurato.')
    return path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_file(relative_path, expected_sha256):
    path = source_file(relative_path)
    data = path.read_bytes()
    if digest(data) != expected_sha256:
        raise ValueError('File cambiato: rileggilo e richiedi una nuova approvazione.')
    return path, data


def publish_bytes(destination, data, *, replace=False):
    # Publish complete files. A concurrent destination is never overwritten by a copy.
    fd, name = tempfile.mkstemp(dir=destination.parent, prefix='.cora-staging-')
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def archive_previous(path, data, *, move=False):
    from search_agent.search_tools import KNOWLEDGE_ROOT
    area = trash_area(KNOWLEDGE_ROOT)
    identifier = uuid.uuid4().hex
    slot = confined_path(area, area/identifier)
    slot.mkdir()
    metadata = {'id':identifier, 'path':path.relative_to(KNOWLEDGE_ROOT).as_posix(),
                'deletedAt':datetime.now(timezone.utc).isoformat(), 'reason':'agent-trash' if move else 'before-edit'}
    (slot/'metadata.json').write_text(json.dumps(metadata), encoding='utf-8')
    if move:
        path.rename(slot/'content')
    else:
        publish_bytes(slot/'content', data)
    return metadata


@agent_tool('supervisor', capability='library_file_info', actions=('library_read',), effect='read', retry='safe')
def library_file_info(relative_path: str) -> dict:
    """Legge dimensione e SHA256 del file nella Libreria IA prima di proporre una modifica o il cestino."""
    with operation():
        path = source_file(relative_path)
        data = path.read_bytes()
        return {'path':relative_path, 'sha256':digest(data), 'size_bytes':len(data)}


@agent_tool('supervisor', capability='library_copy', actions=('library_read', 'library_copy'), effect='write', retry='never')
def library_copy(relative_path: str, destination: str) -> dict:
    """Crea una copia nella sola Libreria IA. Non modifica l'origine; assegna un nome libero se già occupato."""
    from search_agent.search_tools import _safe_path, KNOWLEDGE_ROOT
    with operation():
        ensure_runtime_active()
        source = source_file(relative_path)
        data = source.read_bytes()
        requested = _safe_path(destination)
        if not requested.parent.is_dir() or requested == KNOWLEDGE_ROOT:
            raise ValueError('La cartella di destinazione deve già esistere.')
        for index in range(1000):
            target = requested if index == 0 else requested.with_name(f'{requested.stem} ({index}){requested.suffix}')
            target = _safe_path(target.relative_to(KNOWLEDGE_ROOT).as_posix())
            try:
                publish_bytes(target, data)
                return {'status':'ok', 'path':target.relative_to(KNOWLEDGE_ROOT).as_posix(), 'source':relative_path}
            except FileExistsError:
                continue
        raise ValueError('Troppi nomi occupati: scegli una destinazione diversa.')


@agent_tool('supervisor', capability='library_replace_text', actions=('library_read', 'library_modify'), effect='write', retry='never')
def library_replace_text(relative_path: str, expected_sha256: str, old_text: str, new_text: str) -> dict:
    """Propone la sostituzione di un singolo estratto testuale UTF-8. Mostra prima/dopo in Attività; esegue solo dopo conferma sulla stessa versione SHA256."""
    from search_agent.search_tools import TEXT_EXTENSIONS, MAX_FILE_BYTES
    with operation():
        ensure_runtime_active()
        path, data = checked_file(relative_path, expected_sha256)
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            raise ValueError('Modifica puntuale disponibile solo per file testuali UTF-8; non PDF o Word.')
        text = data.decode('utf-8')
        if not old_text or text.count(old_text) != 1:
            raise ValueError('Il testo da sostituire deve essere presente una sola volta.')
        updated = text.replace(old_text, new_text, 1).encode('utf-8')
        if len(updated) > MAX_FILE_BYTES or updated == data:
            raise ValueError('Modifica vuota o oltre il limite di dimensione.')
        backup = archive_previous(path, data)
        publish_bytes(path, updated, replace=True)
        return {'status':'ok', 'path':relative_path, 'sha256':digest(updated), 'previous_version_trash_id':backup['id']}


@agent_tool('supervisor', capability='library_trash', actions=('library_read', 'library_trash'), effect='write', retry='never')
def library_trash(relative_path: str, expected_sha256: str) -> dict:
    """Propone lo spostamento di un file della Libreria IA nel cestino, solo dopo conferma sulla versione letta. Nessuna eliminazione definitiva."""
    with operation():
        ensure_runtime_active()
        path, data = checked_file(relative_path, expected_sha256)
        return {'status':'ok', 'trash':archive_previous(path, data, move=True)}


LIBRARY_WRITE_TOOLS = [library_file_info, library_copy, library_replace_text, library_trash]
