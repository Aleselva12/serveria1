"""Owner-facing filesystem API. Does not expose files to agents or index them."""
from __future__ import annotations

import hmac
import json
import mimetypes
import os
import shutil
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.file_paths import ORIGINALS_ID, original_resource

BASE = Path(__file__).resolve().parent.parent
RESERVED = {".cora-trash", ".cora-staging"}
LOCK = threading.RLock()


def owner_access(request: Request):
    token = os.getenv("CORA_FILES_TOKEN", "")
    if token:
        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied, "Bearer " + token):
            raise HTTPException(401, "Accesso File server non autorizzato.")
    elif not request.client or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "Configura CORA_FILES_TOKEN per l'accesso remoto.")


def roots():
    raw = os.getenv("CORA_FILE_ROOTS", "").strip()
    if not raw:
        path = BASE / "data" / "server_files"
        path.mkdir(parents=True, exist_ok=True)
        return [{"id": "files", "label": "File server", "path": str(path), "writable": True}, original_resource()]
    try:
        items = json.loads(raw)
        assert isinstance(items, list) and items
        ids = set()
        result = []
        for item in items:
            assert isinstance(item, dict)
            ident = item["id"]
            assert isinstance(ident, str) and ident and ident not in ids and ident != ORIGINALS_ID
            assert isinstance(item["path"], str) and item["path"]
            assert isinstance(item.get("writable", False), bool)
            label = item.get("label", ident)
            assert isinstance(label, str)
            ids.add(ident)
            path = Path(item["path"]).expanduser()
            if not path.is_absolute():
                path = BASE / path
            result.append({"id": ident, "label": label, "path": str(path.resolve()), "writable": item.get("writable", False)})
        return result + [original_resource()]
    except (ValueError, KeyError, TypeError, AssertionError):
        raise HTTPException(503, "Configurazione CORA_FILE_ROOTS non valida.") from None


def root_for(root_id: str, write: bool = False, root_provider=roots):
    root = next((r for r in root_provider() if r["id"] == root_id), None)
    if root is None:
        raise HTTPException(404, "Risorsa non configurata.")
    if write and not root["writable"]:
        raise HTTPException(403, "Risorsa in sola lettura.")
    base = Path(root["path"])
    if not base.is_dir():
        raise HTTPException(503, "Cartella del server non disponibile.")
    return root, base


def parts(path: str):
    # Same syntax on Windows and Linux. Never interpret a client path as an absolute host path.
    if path.startswith("/") or "\\" in path or ":" in path or "\x00" in path:
        raise HTTPException(400, "Percorso relativo non valido.")
    segments = path.split("/") if path else []
    if any(p in {"", ".", ".."} or p in RESERVED for p in segments):
        raise HTTPException(400, "Percorso relativo non valido.")
    return segments


def resolve(base: Path, path: str):
    target = base
    for segment in parts(path):
        target = target / segment
        if target.is_symlink():
            raise HTTPException(403, "I collegamenti simbolici non sono navigabili.")
    if not target.resolve().is_relative_to(base.resolve()):
        raise HTTPException(403, "Percorso esterno alla risorsa.")
    return target


def exists(path: Path):
    if not path.exists():
        raise HTTPException(404, "File o cartella non trovato.")


def vacant(path: Path):
    if path.exists() or path.is_symlink():
        raise HTTPException(409, "Esiste già un elemento con questo nome.")
    if not path.parent.is_dir():
        raise HTTPException(404, "Cartella di destinazione non trovata.")


@contextmanager
def operation():
    with LOCK:
        try:
            yield
        except PermissionError:
            raise HTTPException(403, "Permessi del sistema operativo insufficienti.") from None
        except OSError:
            raise HTTPException(503, "Operazione non riuscita sul filesystem del server.") from None


def iso(timestamp: float):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def node(base: Path, target: Path, writable: bool):
    stat = target.lstat()
    path = target.relative_to(base).as_posix()
    kind = "link" if target.is_symlink() else "folder" if target.is_dir() else "file" if target.is_file() else "special"
    return {"path": path, "name": target.name, "kind": kind,
            "sizeBytes": stat.st_size if kind == "file" else None,
            "modifiedAt": iso(stat.st_mtime),
            "mimeType": mimetypes.guess_type(target.name)[0] or "application/octet-stream",
            "capabilities": ([] if kind in {"link", "special"} else
                             (["read", "upload", "mkdir"] if kind == "folder" and writable else ["read"] if kind == "folder" else ["download"]) +
                             (["rename", "move", "copy", "trash"] if writable else []))}


def upload_to(root: dict, base: Path, path: str, file: UploadFile):
    # Spool to disk; publish only completed uploads. Never overwrite an existing file.
    with operation():
        folder = resolve(base, path)
        exists(folder)
        if not folder.is_dir():
            raise HTTPException(400, "Destinazione non valida.")
        name = file.filename or ""
        if len(parts(name)) != 1:
            raise HTTPException(400, "Nome file non valido.")
        target = resolve(base, "/".join(filter(None, [path, name])))
        vacant(target)
        staging = base / ".cora-staging"
        if staging.is_symlink():
            raise HTTPException(403, "Area temporanea non valida.")
        staging.mkdir(exist_ok=True)
        try:
            limit = int(os.getenv("CORA_FILES_MAX_UPLOAD_BYTES", "1073741824"))
            if limit < 1:
                raise ValueError
        except ValueError:
            raise HTTPException(503, "Limite upload non valido.") from None
        fd, tempname = tempfile.mkstemp(dir=staging)
        temp = Path(tempname)
        try:
            size = 0
            with os.fdopen(fd, "wb") as out:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise HTTPException(413, "File oltre il limite di upload configurato.")
                    out.write(chunk)
            try:
                os.link(temp, target)  # Atomic no-clobber publication on the same volume.
            except FileExistsError:
                raise HTTPException(409, "Esiste già un elemento con questo nome.") from None
        finally:
            temp.unlink(missing_ok=True)
            file.file.close()
        return node(base, target, root["writable"])


def trash_area(base: Path):
    area = base / ".cora-trash"
    if area.is_symlink():
        raise HTTPException(403, "Cestino non valido.")
    area.mkdir(exist_ok=True)
    return area


class Location(BaseModel):
    root_id: str
    path: str = Field(min_length=1)


class Transfer(Location):
    destination: str = Field(min_length=1)
    mode: str = "move"


class Restore(BaseModel):
    root_id: str
    id: str


def make_router(prefix: str, label: str, root_provider=roots, *, allow_upload=True):
    router = APIRouter(prefix=prefix, tags=[label], dependencies=[Depends(owner_access)])

    def select_root(root_id: str, write: bool = False):
        return root_for(root_id, write, root_provider)

    @router.get("/roots")
    def list_roots():
        with operation():
            result = []
            for root in root_provider():
                base = Path(root["path"])
                available = base.is_dir()
                storage = None
                if available:
                    try:
                        usage = shutil.disk_usage(base)
                        storage = {"usedBytes": usage.used, "totalBytes": usage.total, "freeBytes": usage.free}
                    except OSError:
                        available = False
                result.append({**root, "available": available, "storage": storage})
            return {"roots": result}


    @router.get("/children")
    def children(root_id: str, path: str = "", query: str = "", offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
        with operation():
            root, base = select_root(root_id)
            target = resolve(base, path)
            exists(target)
            if not target.is_dir():
                raise HTTPException(400, "Il percorso non è una cartella.")
            entries = []
            for child in target.iterdir():
                if child.name in RESERVED or not query.casefold() in child.name.casefold():
                    continue
                try:
                    entries.append(node(base, child, root["writable"]))
                except FileNotFoundError:
                    continue
            entries.sort(key=lambda n: (n["kind"] != "folder", n["name"].casefold(), n["name"]))
            return {"rootId": root_id, "path": path, "parentPath": path.rpartition("/")[0] if path else None,
                    "writable": root["writable"], "total": len(entries), "items": entries[offset:offset + limit]}


    @router.get("/download")
    def download(root_id: str, path: str):
        with operation():
            _, base = select_root(root_id)
            target = resolve(base, path)
            exists(target)
            if not target.is_file():
                raise HTTPException(400, "Seleziona un file normale.")
            return FileResponse(target, filename=target.name, media_type="application/octet-stream")


    @router.post("/folders", status_code=201)
    def mkdir(body: Location):
        with operation():
            root, base = select_root(body.root_id, write=True)
            target = resolve(base, body.path)
            vacant(target)
            target.mkdir()
            return node(base, target, root["writable"])


    if allow_upload:
        @router.post("/upload", status_code=201)
        def upload(root_id: str = Form(...), path: str = Form(""), file: UploadFile = File(...)):
            root, base = select_root(root_id, write=True)
            return upload_to(root, base, path, file)



    @router.post("/transfer")
    def transfer(body: Transfer):
        with operation():
            if body.mode not in {"move", "copy"}:
                raise HTTPException(400, "Modalità non valida.")
            root, base = select_root(body.root_id, write=True)
            src = resolve(base, body.path)
            dst = resolve(base, body.destination)
            exists(src)
            vacant(dst)
            if dst.is_relative_to(src):
                raise HTTPException(400, "Non puoi spostare o copiare una cartella dentro se stessa.")
            if not src.is_file() and not src.is_dir():
                raise HTTPException(400, "Tipo di file non supportato.")
            if src.is_dir():
                for directory, directories, files in os.walk(src, followlinks=False):
                    for name in directories + files:
                        child = Path(directory) / name
                        if child.is_symlink() or (not child.is_dir() and not child.is_file()) or name in RESERVED:
                            raise HTTPException(403, "La cartella contiene collegamenti, file speciali o aree riservate.")
            if body.mode == "move":
                src.rename(dst)
            elif src.is_dir():
                try:
                    dst.mkdir()  # Reserve destination; do not clean up a pre-existing folder.
                except FileExistsError:
                    raise HTTPException(409, "Destinazione già esistente.") from None
                try:
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                except Exception:
                    if dst.exists():
                        shutil.rmtree(dst)
                    raise
            else:
                try:
                    with src.open("rb") as reader, dst.open("xb") as writer:
                        shutil.copyfileobj(reader, writer)
                except FileExistsError:
                    raise HTTPException(409, "Destinazione già esistente.") from None
                except Exception:
                    dst.unlink(missing_ok=True)
                    raise
            return node(base, dst, root["writable"])


    @router.post("/trash", status_code=201)
    def trash(body: Location):
        with operation():
            _, base = select_root(body.root_id, write=True)
            src = resolve(base, body.path)
            exists(src)
            item_id = uuid.uuid4().hex
            slot = trash_area(base) / item_id
            slot.mkdir()
            metadata = {"id": item_id, "path": body.path, "deletedAt": datetime.now(timezone.utc).isoformat()}
            try:
                (slot / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
                src.rename(slot / "content")
            except Exception:
                shutil.rmtree(slot)
                raise
            return metadata


    @router.get("/trash")
    def list_trash(root_id: str):
        with operation():
            _, base = select_root(root_id)
            area = base / ".cora-trash"
            if area.is_symlink():
                raise HTTPException(403, "Cestino non valido.")
            items = []
            if area.is_dir():
                for slot in area.iterdir():
                    if slot.is_symlink() or not slot.is_dir():
                        continue
                    metadata = slot / "metadata.json"
                    if metadata.is_symlink():
                        continue
                    try:
                        data = json.loads(metadata.read_text(encoding="utf-8"))
                        if (slot / "content").exists():
                            items.append(data)
                    except (ValueError, OSError):
                        continue
            return {"items": sorted(items, key=lambda i: i["deletedAt"], reverse=True)}


    @router.post("/restore")
    def restore(body: Restore):
        with operation():
            if len(body.id) != 32 or any(c not in "0123456789abcdef" for c in body.id):
                raise HTTPException(400, "Identificativo cestino non valido.")
            root, base = select_root(body.root_id, write=True)
            slot = trash_area(base) / body.id
            if slot.is_symlink() or (slot / "metadata.json").is_symlink() or (slot / "content").is_symlink():
                raise HTTPException(403, "Elemento cestino non valido.")
            exists(slot / "content")
            try:
                data = json.loads((slot / "metadata.json").read_text(encoding="utf-8"))
                dst = resolve(base, data["path"])
            except (ValueError, KeyError, TypeError):
                raise HTTPException(409, "Metadati cestino non validi.") from None
            vacant(dst)
            (slot / "content").rename(dst)
            (slot / "metadata.json").unlink()
            slot.rmdir()
            return node(base, dst, root["writable"])

    return router


router = make_router("/api/v1/server/files", "File server")
