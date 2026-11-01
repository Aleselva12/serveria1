"""Small owner-only UTF-8 edits with optimistic concurrency and byte backups."""
import hashlib
import os
import stat
import tempfile
import uuid
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, Field

MAX_BYTES = 1024 * 1024


class TextEdit(BaseModel):
    root_id: str
    path: str = Field(min_length=1)
    revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    text: str = Field(max_length=MAX_BYTES)


def read_text(target):
    if not target.is_file():
        raise HTTPException(400, 'Seleziona un file normale.')
    with target.open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, 'Editor disponibile per file fino a 1 MiB.')
    try:
        text = data.decode('utf-8')
        if any(ord(c) < 32 and c not in '\t\r\n' for c in text):
            raise ValueError
    except (UnicodeError, ValueError):
        raise HTTPException(415, 'L’editor richiede un file di testo UTF-8, senza dati binari.') from None
    return data, text


def revision(data):
    return hashlib.sha256(data).hexdigest()


def register_editor(router, root_provider):
    from core.server_files import operation, root_for, resolve, exists

    @router.get('/text')
    def open_text(root_id: str, path: str):
        with operation():
            _, base = root_for(root_id, root_provider=root_provider)
            target = resolve(base, path)
            exists(target)
            data, text = read_text(target)
            from fastapi.responses import JSONResponse
            return JSONResponse({'text': text, 'revision': revision(data)},
                                headers={'Cache-Control': 'private, no-store'})

    @router.post('/text')
    def save_text(body: TextEdit):
        with operation():
            _, base = root_for(body.root_id, write=True, root_provider=root_provider)
            target = resolve(base, body.path)
            exists(target)
            original, _ = read_text(target)
            before = target.stat()
            if before.st_nlink != 1:
                raise HTTPException(409, 'File con collegamenti fisici: modifica tramite SSH.')
            if revision(original) != body.revision:
                raise HTTPException(409, 'Il file è cambiato dopo l’apertura. Conserva le tue modifiche e riapri il file.')
            try:
                data = body.text.encode('utf-8')
            except UnicodeError:
                raise HTTPException(422, 'Testo UTF-8 non valido.') from None
            if len(data) > MAX_BYTES:
                raise HTTPException(413, 'Editor disponibile per file fino a 1 MiB.')
            if any(ord(c) < 32 and c not in '\t\r\n' for c in body.text):
                raise HTTPException(415, 'Il testo contiene dati binari.')
            return save_bytes(base, body.path, original, data, body.revision)


def save_bytes(base, path, original, data, expected_revision):
    """Called under the filesystem operation lock; never overwrite a stale revision."""
    from core.server_files import resolve, exists
    target = resolve(base, path)
    exists(target)
    before = target.stat()
    if not target.is_file() or before.st_nlink != 1:
        raise HTTPException(409, 'Seleziona un file normale senza collegamenti fisici.')
    if revision(original) != expected_revision:
        raise HTTPException(409, 'Il file è cambiato dopo l’apertura. Conserva la bozza e riapri il file.')
    # Short backup names also work for source filenames near NAME_MAX.
    backup = resolve(base, (target.parent.relative_to(base) / ('cora-backup-' + uuid.uuid4().hex + '.bak')).as_posix())
    fd, name = tempfile.mkstemp(prefix='.cora-edit-', dir=target.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temp, stat.S_IMODE(before.st_mode))
        # Keep ownership; if not permitted, leave the original untouched.
        if hasattr(os, 'chown'):
            current = temp.stat()
            if (current.st_uid, current.st_gid) != (before.st_uid, before.st_gid):
                os.chown(temp, before.st_uid, before.st_gid)
        with backup.open('xb') as out:
            os.chmod(backup, 0o600)
            out.write(original)
            out.flush()
            os.fsync(out.fileno())
        # Recheck external edits immediately before publishing.
        resolve(base, path)
        current = target.stat()
        if (before.st_ino, before.st_mtime_ns, before.st_size) != (current.st_ino, current.st_mtime_ns, current.st_size) or target.read_bytes() != original:
            raise HTTPException(409, 'File modificato durante il salvataggio. Riaprilo prima di riprovare.')
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return {'revision': revision(data), 'backupPath': backup.relative_to(base).as_posix()}
