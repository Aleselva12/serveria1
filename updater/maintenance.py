"""Fixed updater lifecycle protocol; candidate sources come only from host Git.

Two commits are accepted as a source for the updater package:

* the active Cora commit (owner-requested alignment, ``core.host_maintenance``);
* the commit of the release an ``apply`` job is about to install. The engine
  hands off to that package *before* stopping Cora, so a release that needs a
  newer updater is always installed by the updater it ships with.

Both come from the private host repository; the browser never supplies a URL,
path, script or arbitrary ref.
"""
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from updater.engine import atomic

PACKAGE = Path(__file__).resolve().parent


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


def installed_digest():
    return digest(PACKAGE)


def export(repo, commit, destination):
    """Write the exact updater/*.py blobs of ``commit`` under ``destination/updater``."""
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Versione non valida')
    package = Path(destination)/'updater'
    package.mkdir(parents=True)
    # No arbitrary ref, archive paths, symlinks, executable hooks or dependencies.
    entries = subprocess.check_output(['git', '--git-dir', str(repo), 'ls-tree', '-r', commit, '--', 'updater'],
                                      timeout=30, text=True).splitlines()
    for entry in entries:
        meta, name = entry.split('\t', 1)
        mode, kind, _oid = meta.split()
        path = Path(name)
        if path.suffix != '.py':
            continue
        if mode != '100644' or kind != 'blob' or '..' in path.parts:
            raise ValueError('Sorgente updater non regolare')
        target = Path(destination)/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(subprocess.check_output(['git', '--git-dir', str(repo), 'show', commit+':'+name], timeout=30))
    if not (package/'service.py').is_file():
        raise ValueError('Sorgenti updater assenti nella versione richiesta')
    return package


def commit_digest(repo, commit):
    with tempfile.TemporaryDirectory(prefix='updater-digest-') as temporary:
        return digest(export(repo, commit, temporary))


def status(root):
    root = Path(root)
    result = {'available': (root/'maintenance.enabled').is_file(),
              'digest': installed_digest(), 'pending': (root/'maintenance.request').exists()}
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


def _stage(engine, apps, commit, expected, *, handoff_job=None):
    """Validate, export and queue a package switch. Caller holds no lock."""
    root = engine.root
    if not re.fullmatch('[0-9a-f]{40}', commit) or not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('Versione non valida')
    with engine.lock, idle_apps(apps):
        if getattr(apps, 'nextcloud', None) is not None and apps.nextcloud.job['status'] in {'running', 'recovery_required'}:
            raise ValueError('Completare o recuperare prima la manutenzione Nextcloud')
        if not (root/'maintenance.enabled').is_file():
            raise ValueError('Installare prima il servizio host-maintenance')
        if (root/'maintenance.request').exists():
            raise ValueError('Manutenzione già in corso')
        others = [j for j in engine.list_jobs() if handoff_job is None or j.get('id') != handoff_job]
        if any(j['status'] in {'queued', 'running', 'recovery_required'} for j in others):
            raise ValueError('Attendere la conclusione dei job updater')
        if handoff_job is None and engine.current()['commit'] != commit:
            raise ValueError('Cora e rilascio host non allineati')
        if installed_digest() == expected:
            return {'status': 'compatible', 'digest': expected}
        candidate = root/'maintenance.next'
        if candidate.exists():
            shutil.rmtree(candidate)
        package = export(engine.repo, commit, candidate)
        if digest(package) != expected:
            raise ValueError('Sorgenti host diversi dalla versione richiesta')
        for file in package.rglob('*.py'):
            compile(file.read_bytes(), str(file), 'exec')
        request = {'commit': commit, 'digest': expected}
        if handoff_job:
            request['handoff_job'] = handoff_job
        atomic(root/'maintenance.request', request)
        return {'status': 'queued', 'digest': expected}


def submit(engine, apps, commit, expected):
    """Owner-requested alignment with the active Cora commit."""
    return _stage(engine, apps, commit, expected)


def handoff(engine, apps, job_id, commit, expected):
    """Queue the updater shipped with the release that ``job_id`` is about to apply.

    The job must be a running ``apply`` of a ready release for ``commit``; the
    engine requeues it right before calling this function.
    """
    row = engine.load(job_id)
    release = engine.load(row['release_id'])
    if row['kind'] != 'apply' or row['commit'] != commit or release.get('commit') != commit \
            or release.get('kind') != 'prepare' or release.get('status') != 'ready':
        raise ValueError('Rilascio non valido per aggiornare l\'updater')
    return _stage(engine, apps, commit, expected, handoff_job=job_id)
