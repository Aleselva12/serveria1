"""Opt-in lightweight folder monitor. No Ollama, no file changes."""
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from core.file_paths import knowledge_root, originals_root
from search_agent.search_tools import _safe_path, BLOCKED_PARTS, BLOCKED_NAMES

_LOCK = threading.RLock()
_STOP = threading.Event()
_THREAD = None
MAX_FILES = 5000

def _state_path():
    # Original uploads are stored separately from the working Library.
    base = originals_root()
    base.mkdir(parents=True, exist_ok=True)
    return base / '.cora-library-monitor.json'

def _read():
    path = _state_path()
    if not path.exists():
        return {'folders': [], 'snapshot': {}, 'events': [], 'last_scan': None}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return {key: data.get(key, default) for key,default in
                [('folders',[]), ('snapshot',{}), ('events',[]), ('last_scan',None)]}
    except (ValueError, TypeError, OSError):
        raise RuntimeError('Registro Library Monitor non leggibile; non verrà sovrascritto.')

def _save(data):
    path = _state_path()
    temp = path.with_name(path.name + '.tmp')
    try:
        with temp.open('w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, separators=(',', ':'))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

def normalize_folder(folder):
    if not isinstance(folder, str) or not folder.strip() or folder.strip() == '.':
        raise ValueError('Seleziona una sottocartella della Libreria IA.')
    candidate = _safe_path(folder)
    if not candidate.is_dir() or candidate.is_symlink():
        raise ValueError('Cartella non disponibile o collegamento non permesso.')
    return candidate.relative_to(knowledge_root()).as_posix()

def status():
    with _LOCK:
        data = _read()
        return {'folders': list(data['folders']), 'last_scan': data['last_scan'],
                'events': list(data['events'][-50:]), 'indexed_files': len(data['snapshot'])}

def set_folder(folder, enabled):
    name = normalize_folder(folder)
    with _LOCK:
        data = _read()
        folders = set(data['folders'])
        if enabled: folders.add(name)
        else: folders.discard(name)
        data['folders'] = sorted(folders)
        # Drop stale records on next scan; no mutations to actual documents.
        _save(data)
    return status()

def scan_once():
    with _LOCK:
        data = _read()
        snapshot = {}
        root = knowledge_root()
        visited = 0
        for folder in data['folders']:
            try:
                base = _safe_path(folder)
                if not base.is_dir(): continue
                for current, dirs, files in os.walk(base, followlinks=False):
                    dirs[:] = sorted(d for d in dirs if d not in BLOCKED_PARTS
                                     and not (Path(current)/d).is_symlink())
                    for filename in files:
                        if _STOP.is_set(): return False
                        visited += 1
                        if visited > MAX_FILES: return False  # Do not persist incomplete scans.
                        path = Path(current)/filename
                        if path.is_symlink() or filename.lower() in BLOCKED_NAMES or filename.startswith('.'):
                            continue
                        try:
                            stat = path.stat()
                            relative = path.relative_to(root).as_posix()
                            snapshot[relative] = [stat.st_size, stat.st_mtime_ns]
                        except (OSError, ValueError):
                            continue
            except (OSError, ValueError):
                continue
        before = data['snapshot']
        changes = []
        for path, meta in snapshot.items():
            if path not in before: changes.append({'type':'added','path':path})
            elif before[path] != meta: changes.append({'type':'changed','path':path})
        monitored = tuple(data['folders'])
        for path in before:
            if path not in snapshot and any(path.startswith(folder + '/') for folder in monitored):
                changes.append({'type':'removed_or_unwatched','path':path})
        # A file disappearing during scan may mean deletion or access failure; do not claim deletion.
        now = datetime.now(timezone.utc).isoformat()
        if data['last_scan'] is not None:
            data['events'] = (data['events'] + [{'at':now, **item} for item in changes])[-100:]
        data['snapshot'] = snapshot
        data['last_scan'] = now
        _save(data)
        return True

def _loop():
    while not _STOP.wait(max(60, int(os.getenv('CORA_LIBRARY_SCAN_SECONDS','300')))):
        try: scan_once()
        except Exception:
            # Leave the previous snapshot untouched and retry later.
            pass

def start():
    global _THREAD
    if _THREAD and _THREAD.is_alive(): return
    _STOP.clear()
    _THREAD = threading.Thread(target=_loop, daemon=True, name='cora-library-monitor')
    _THREAD.start()

def stop():
    _STOP.set()
    if _THREAD: _THREAD.join(timeout=2)
