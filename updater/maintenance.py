"""Fixed updater lifecycle protocol; candidate sources come only from active host Git."""
import hashlib
import json
import re
from contextlib import contextmanager
from pathlib import Path

from updater.engine import atomic


def digest(folder):
    files = sorted(Path(folder).rglob('*.py'))
    if not files:
        raise ValueError('Sorgenti updater mancanti')
    value = hashlib.sha256()
    for file in files:
        if file.is_symlink():
            raise ValueError('Link non ammesso nei sorgenti updater')
        value.update(file.relative_to(folder).as_posix().encode() + b'\0' + file.read_bytes() + b'\0')
    return value.hexdigest()


def status(root):
    root = Path(root)
    result = {'available': (root/'maintenance.enabled').is_file(),
              'digest': digest(Path(__file__).parent), 'pending': (root/'maintenance.request').exists()}
    if (root/'maintenance.result.json').exists():
        result['lastUpdate'] = json.loads((root/'maintenance.result.json').read_text())
    return result


@contextmanager
def idle_apps(apps):
    if not apps.lock.acquire(blocking=False):
        raise ValueError('Attendere aggiornamento applicazioni in corso')
    try:
        yield
    finally:
        apps.lock.release()


def submit(engine, apps, commit, expected):
    import shutil
    import subprocess
    root = engine.root
    if not re.fullmatch('[0-9a-f]{40}', commit) or not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('Versione non valida')
    with engine.lock, idle_apps(apps):
        if getattr(apps,'nextcloud',None) is not None and apps.nextcloud.job['status'] in {'running','recovery_required'}:
            raise ValueError('Completare o recuperare prima la manutenzione Nextcloud')
        if not (root/'maintenance.enabled').is_file():
            raise ValueError('Installare prima il servizio host-maintenance')
        if (root/'maintenance.request').exists():
            raise ValueError('Manutenzione già in corso')
        if any(j['status'] in {'queued','running','recovery_required'} for j in engine.list_jobs()):
            raise ValueError('Attendere la conclusione dei job updater')
        if engine.current()['commit'] != commit:
            raise ValueError('Cora e rilascio host non allineati')
        if digest(Path(__file__).parent) == expected:
            return {'status': 'compatible', 'digest': expected}
        candidate = root/'maintenance.next'
        if candidate.exists():
            shutil.rmtree(candidate)
        package = candidate/'updater'
        package.mkdir(parents=True)
        # No arbitrary ref, archive paths, symlinks, executable hooks or dependencies.
        entries = subprocess.check_output(['git','--git-dir',str(engine.repo),'ls-tree','-r',commit,'--','updater'], timeout=30, text=True).splitlines()
        for entry in entries:
            meta, name = entry.split('\t',1)
            mode, kind, oid = meta.split()
            path = Path(name)
            if path.suffix != '.py':
                continue
            if mode != '100644' or kind != 'blob' or '..' in path.parts:
                raise ValueError('Sorgente updater non regolare')
            target = candidate/path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(subprocess.check_output(['git','--git-dir',str(engine.repo),'show',commit+':'+name], timeout=30))
        if not (package/'service.py').is_file() or digest(package) != expected:
            raise ValueError('Sorgenti host diversi dalla versione richiesta')
        for file in package.rglob('*.py'):
            compile(file.read_bytes(), str(file), 'exec')
        atomic(root/'maintenance.request', {'commit':commit,'digest':expected})
        return {'status':'queued','digest':expected}
