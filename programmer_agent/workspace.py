"""Bounded source snapshots and optimistic writes outside the live repository."""
from __future__ import annotations

import contextvars
import difflib
import hashlib
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

PROJECT = Path(__file__).resolve().parents[1]
LOCK = threading.RLock()
CURRENT = contextvars.ContextVar("programmer_workspace", default=None)
MAX_FILE = 1_000_000
MAX_FILES = 6000
MAX_TOTAL = 40_000_000
SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".json", ".md", ".txt", ".css", ".html", ".yml", ".yaml", ".toml", ".sql", ".ini", ".cfg", ".ps1", ".cmd", ".sh", ".conf", ".lock", ".svg", ".example", ".service"}
EXCLUDED = {"data", "state", "backups", "logs", "knowledge", "audio", "models", "quotes", "structure_workspace", "programmer_workspace", "node_modules", "dist", "venv", "env", "__pycache__"}


class WorkspaceConflict(ValueError):
    pass


def root() -> Path:
    result = Path(os.getenv("CORA_PROGRAMMER_WORKSPACE_ROOT") or PROJECT / "data" / "programmer").expanduser().absolute()
    _no_links(result)
    result = result.resolve()
    # Workspaces contain generated source: refuse an ancestor/equal of live source.
    if result == PROJECT or result in PROJECT.parents:
        raise ValueError("Il workspace deve essere separato dal codice attivo.")
    if PROJECT in result.parents and result.relative_to(PROJECT).parts[0] != "data":
        raise ValueError("Dentro il progetto sono consentiti soltanto workspace nella cartella data.")
    return result


def safe_name(relative: str) -> str:
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise ValueError("Usa un percorso relativo POSIX.")
    path = PurePosixPath(relative)
    if path.is_absolute() or any(p in {"..", "."} or p.startswith(".") and p not in {".github", ".gitignore", ".dockerignore", ".env.example"} for p in path.parts):
        raise ValueError("Percorso non autorizzato.")
    if any(p.lower() in EXCLUDED for p in path.parts):
        raise ValueError("Cartella privata o generata esclusa.")
    name = path.name.lower()
    if (name.endswith(".json") and any(word in name for word in ("credential", "token", "secret"))) or (".env" in name and not name.endswith(".env.example")) or path.suffix.lower() not in SUFFIXES and name not in {"dockerfile", "makefile", ".gitignore", ".dockerignore"} and not name.endswith(".dockerfile"):
        raise ValueError("Tipo di file o nome riservato.")
    return path.as_posix()


def _no_links(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("I link simbolici non sono autorizzati.")


def directory(identifier: str) -> Path:
    identifier = str(UUID(identifier))
    path = root() / identifier
    _no_links(path)
    if not path.is_dir() or not (path / "manifest.json").is_file():
        raise FileNotFoundError("Workspace non trovato.")
    return path


def file_path(identifier: str, relative: str, area: str = "files") -> Path:
    path = directory(identifier) / area / safe_name(relative)
    _no_links(path)
    return path


def digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _atomic(path: Path, content: str) -> None:
    _no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            os.fchmod(stream.fileno(), 0o644) if hasattr(os, "fchmod") else None
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def source_files(project: Path = PROJECT):
    workspace_root = root()
    for folder, dirs, names in os.walk(project, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d.lower() not in EXCLUDED
                         and not (Path(folder) / d).is_symlink()
                         and (Path(folder) / d).absolute() != workspace_root)
        for name in sorted(names):
            path = Path(folder) / name
            try:
                relative = safe_name(path.relative_to(project).as_posix())
                _no_links(path)
                if path.stat().st_size > MAX_FILE:
                    continue
                yield relative, path.read_text(encoding="utf-8")
            except (ValueError, OSError, UnicodeError):
                continue


def create(title: str, project: Path = PROJECT) -> dict:
    title = title.strip()
    if not 1 <= len(title) <= 120:
        raise ValueError("Titolo da 1 a 120 caratteri.")
    with LOCK:
        identifier = str(uuid4())
        target = root() / identifier
        _no_links(target)
        files = list(source_files(project))
        if len(files) > MAX_FILES or sum(len(c.encode("utf-8")) for _, c in files) > MAX_TOTAL:
            raise ValueError("Snapshot oltre il limite: riduci il progetto prima di creare il workspace.")
        target.mkdir(parents=True)
        manifest = {"id": identifier, "title": title, "created_at": datetime.now(timezone.utc).isoformat(),
                    "source_digest": digest(json.dumps([(p, digest(c)) for p, c in files])), "file_count": len(files),
                    "baseline": {p: digest(c) for p, c in files}, "status": "draft"}
        for relative, content in files:
            _atomic(target / "files" / relative, content)
            _atomic(target / "baseline" / relative, content)
        (target / "files").mkdir(exist_ok=True)
        _atomic(target / "manifest.json", json.dumps(manifest, ensure_ascii=False))
        return summary(manifest)


def summary(manifest: dict) -> dict:
    return {k: manifest[k] for k in ("id", "title", "created_at", "source_digest", "file_count", "status", "mode", "base_commit", "commit") if k in manifest}


def manifest(identifier: str) -> dict:
    path = directory(identifier) / "manifest.json"
    _no_links(path)
    return json.loads(path.read_text(encoding="utf-8"))


def list_workspaces() -> list[dict]:
    with LOCK:
        rows = []
        _no_links(root())
        for path in root().glob("*/manifest.json"):
            try:
                rows.append(summary(manifest(path.parent.name)))
            except (ValueError, OSError, KeyError):
                continue
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)[:100]


def list_files(identifier: str) -> list[str]:
    base = directory(identifier) / "files"
    _no_links(base)
    files = []
    for folder, dirs, names in os.walk(base, followlinks=False):
        dirs[:] = sorted(d for d in dirs if (not d.startswith(".") or d == ".github") and not (Path(folder) / d).is_symlink())
        for name in sorted(names):
            try:
                relative = safe_name((Path(folder) / name).relative_to(base).as_posix())
                file_path(identifier, relative)
                files.append(relative)
            except ValueError:
                continue
    return sorted(files)


def read(identifier: str, relative: str, start: int = 1, count: int = 120) -> dict:
    if not 1 <= start or not 1 <= count <= 240:
        raise ValueError("Intervallo non valido; massimo 240 righe.")
    with LOCK:
        path = file_path(identifier, relative)
        if path.stat().st_size > MAX_FILE:
            raise ValueError("File troppo grande.")
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        selected = "".join(lines[start - 1:start - 1 + count])
        return {"path": relative, "content": selected, "sha256": digest(content), "start_line": start,
                "total_lines": len(lines), "truncated": start > 1 or start - 1 + count < len(lines)}


def read_full(identifier: str, relative: str) -> dict:
    """Bounded, complete source for manual editing; never save a paginated excerpt."""
    with LOCK:
        path = file_path(identifier, relative)
        if path.stat().st_size > MAX_FILE:
            raise ValueError("File troppo grande.")
        content = path.read_text(encoding="utf-8")
        return {"path": relative, "content": content, "sha256": digest(content),
                "start_line": 1, "total_lines": len(content.splitlines()), "truncated": False}


def write(identifier: str, relative: str, content: str, expected_sha256: str = "") -> dict:
    if len(content.encode("utf-8")) > MAX_FILE:
        raise ValueError("File oltre il limite.")
    with LOCK:
        path = file_path(identifier, relative)
        previous = path.read_text(encoding="utf-8") if path.exists() else None
        if expected_sha256 != (digest(previous) if previous is not None else ""):
            raise WorkspaceConflict("Il file è cambiato. Rileggilo prima di scrivere.")
        paths = list_files(identifier)
        if relative not in paths and len(paths) >= MAX_FILES:
            raise ValueError("Troppi file nel workspace.")
        total = sum(file_path(identifier, p).stat().st_size for p in paths if p != relative)
        if total + len(content.encode("utf-8")) > MAX_TOTAL:
            raise ValueError("Workspace oltre il limite.")
        _atomic(path, content)
        return {"path": relative, "sha256": digest(content), "saved": True, "status": "draft"}


def diff(identifier: str) -> dict:
    with LOCK:
        original = manifest(identifier)["baseline"]
        changes = []
        for relative in sorted(set(original) | set(list_files(identifier))):
            path = file_path(identifier, relative)
            after = path.read_text(encoding="utf-8") if path.exists() else ""
            if relative in original and path.exists() and digest(after) == original[relative]:
                continue
            baseline = file_path(identifier, relative, "baseline")
            before = baseline.read_text(encoding="utf-8") if relative in original else ""
            patch = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                            fromfile="a/" + relative, tofile="b/" + relative))
            changes.append({"path": relative, "kind": "modified" if relative in original and path.exists() else "deleted" if not path.exists() else "added",
                            "patch": patch[:12000], "truncated": len(patch) > 12000})
        return {"workspace_id": identifier, "changes": changes[:100], "total_changes": len(changes), "truncated": len(changes) > 100}


@contextmanager
def bind_workspace(identifier: str):
    directory(identifier)
    token = CURRENT.set(identifier)
    try:
        yield
    finally:
        CURRENT.reset(token)


def current() -> str:
    identifier = CURRENT.get()
    if not identifier:
        raise ValueError("Il programmatore richiede un workspace selezionato nella pagina Programma.")
    return identifier


def delete(identifier: str, relative: str, expected_sha256: str) -> dict:
    with LOCK:
        path=file_path(identifier,relative)
        if digest(path.read_text(encoding="utf-8"))!=expected_sha256:
            raise WorkspaceConflict("Il file è cambiato: rileggilo prima di eliminarlo.")
        path.unlink()
        return {"path":relative,"deleted":True,"status":"draft"}
