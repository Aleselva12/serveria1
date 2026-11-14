"""Read-only view of every host component against the active release.

Answers "is any part of the server older than the version Cora says it runs?"
for the release images (api, web, optional terminal), the updater package and
the host maintenance helper. Nothing here changes state.
"""
import ast
import subprocess
import threading
import time
from pathlib import Path

HELPER = Path('/usr/local/lib/cora-host-maintenance.py')
CACHE_SECONDS = 20
_cache = {'at': 0.0, 'key': None, 'value': None}
_lock = threading.Lock()


def _shape(source):
    """Code shape that ignores formatting and import order (ruff reorderings)."""
    tree = ast.parse(source)
    imports = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = sorted((alias.name, alias.asname or '') for alias in node.names)
            imports.extend((getattr(node, 'module', None) or '', getattr(node, 'level', 0), name) for name in names)
    imports.sort()
    rest = [ast.dump(node) for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
    return imports, rest


def _row(identifier, label, status, installed='', expected='', note=''):
    return {'id': identifier, 'label': label, 'status': status,
            'installed': installed or '', 'expected': expected or '', 'note': note}


def _images(engine, current):
    expected = current.get('images', {})
    rows = []
    labels = {'api': 'Backend (api)', 'web': 'Interfaccia (web)', 'terminal': 'Terminale'}
    for name in engine.release_services():
        try:
            running = engine.running_image(name)
        except Exception:
            running = None
        want = expected.get(name, '')
        if not running:
            rows.append(_row(name, labels[name], 'stopped', '', want, 'Servizio non in esecuzione.'))
        elif not want:
            rows.append(_row(name, labels[name], 'untracked', running, '',
                             'Immagine fuori dai rilasci: verrà ricostruita al prossimo aggiornamento.'))
        elif running != want:
            rows.append(_row(name, labels[name], 'outdated', running, want,
                             'Immagine diversa da quella del rilascio attivo.'))
        else:
            rows.append(_row(name, labels[name], 'ok', running, want))
    return rows


def _updater(engine, commit):
    from updater import maintenance
    installed = maintenance.installed_digest()
    try:
        expected = maintenance.commit_digest(engine.repo, commit)
    except Exception:
        return _row('updater', 'Updater host', 'unknown', installed, '', 'Sorgenti del rilascio attivo non leggibili.')
    pending = (engine.root/'maintenance.request').exists()
    if installed == expected:
        return _row('updater', 'Updater host', 'ok', installed, expected)
    return _row('updater', 'Updater host', 'updating' if pending else 'outdated', installed, expected,
                'Sostituzione in corso.' if pending else
                'Diverso dal rilascio attivo: si allinea al prossimo aggiornamento o con i collaudi.')


def _helper(engine, commit):
    helper = HELPER
    if not helper.is_file():
        return _row('helper', 'Helper manutenzione host', 'missing', '', '',
                    'Non installato: serve la procedura sudo in docs/HOST_MAINTENANCE.md.')
    try:
        reference = subprocess.check_output(['git', '--git-dir', str(engine.repo), 'show',
                                             commit+':updater/host_maintenance.py'], timeout=30)
        same = _shape(helper.read_bytes()) == _shape(reference)
    except Exception:
        return _row('helper', 'Helper manutenzione host', 'unknown', '', '', 'Confronto non riuscito.')
    if same:
        return _row('helper', 'Helper manutenzione host', 'ok')
    return _row('helper', 'Helper manutenzione host', 'outdated', '', '',
                'Non si aggiorna da solo per scelta: aggiornarlo a mano con sudo copiando '
                'updater/host_maintenance.py del rilascio attivo (docs/HOST_MAINTENANCE.md).')


def inspect(engine, *, clock=time.monotonic):
    current = engine.current()
    key = (current.get('commit'), current.get('updated_at'), (engine.root/'maintenance.request').exists())
    with _lock:
        if _cache['value'] is not None and _cache['key'] == key and clock() - _cache['at'] < CACHE_SECONDS:
            return _cache['value']
        rows = _images(engine, current) + [_updater(engine, current['commit']), _helper(engine, current['commit'])]
        value = {'commit': current['commit'], 'components': rows,
                 'aligned': all(row['status'] == 'ok' for row in rows)}
        _cache.update(at=clock(), key=key, value=value)
        return value
