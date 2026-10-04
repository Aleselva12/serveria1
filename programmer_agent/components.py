"""Versioned component records and immutable review handoffs; never activation."""
from __future__ import annotations
import difflib
import io
import json
import zipfile
from datetime import datetime, timezone
from uuid import UUID, uuid4
from programmer_agent import workspace as ws

KINDS = {'tool', 'automation', 'frontend', 'other'}
REQUIRED = {'tool': ['syntax', 'contracts', 'python_tests'], 'automation': ['syntax', 'contracts'],
            'frontend': ['typescript', 'frontend_build'], 'other': ['syntax']}


def now():
    return datetime.now(timezone.utc).isoformat()


def workspace_digest(identifier):
    return ws.digest(json.dumps([(p, ws.digest(ws.file_path(identifier, p).read_text(encoding='utf-8')))
                                 for p in ws.list_files(identifier)]))


def _load(identifier):
    path = ws.directory(identifier) / 'components.json'
    ws._no_links(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []


def _save(identifier, rows):
    ws._atomic(ws.directory(identifier) / 'components.json', json.dumps(rows, ensure_ascii=False))


def _hashes(identifier, paths):
    return {p: ws.digest(ws.file_path(identifier, p).read_text(encoding='utf-8')) for p in paths}


def check_history(identifier):
    path = ws.directory(identifier) / 'checks.json'
    ws._no_links(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []


def describe(identifier, row):
    value = dict(row)
    current = workspace_digest(identifier)
    latest = {r['profile']: r for r in check_history(identifier) if r.get('workspace_digest') == current}
    missing = [p for p in REQUIRED[row['kind']] if not latest.get(p, {}).get('passed')]
    stale = row['workspace_digest'] != current
    value.update(required_checks=REQUIRED[row['kind']], missing_checks=missing, stale=stale,
                 status='draft' if stale or missing else row['status'], recorded_status=row['status'])
    if not stale and not missing and row['status'] in {'draft', 'verified'}:
        value['status'] = 'verified' if not missing else 'draft'
    return value


def listing(identifier):
    with ws.LOCK:
        return [describe(identifier, row) for row in _load(identifier)]


def register(identifier, title, kind, files, dependencies=None, integration='', component_id=''):
    if kind not in KINDS or not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
        raise ValueError('Titolo o tipo componente non valido.')
    if not isinstance(files, list) or not 1 <= len(files) <= 100:
        raise ValueError('Indica da 1 a 100 file del componente, inclusi i test.')
    paths = sorted({ws.safe_name(p) for p in files})
    if kind == 'tool' and not any(p.startswith('tests/') and p.rsplit('/', 1)[-1].startswith('test') and p.endswith('.py') for p in paths):
        raise ValueError('Un tool deve includere almeno un file di test Python in tests/.')
    if not isinstance(integration, str) or not 1 <= len(integration.strip()) <= 12000:
        raise ValueError('Indica le istruzioni di integrazione.')
    dependencies = dependencies or []
    if not isinstance(dependencies, list) or len(dependencies) > 50 or any(not isinstance(d, str) or len(d) > 300 for d in dependencies):
        raise ValueError('Dipendenze non valide.')
    with ws.LOCK:
        hashes = _hashes(identifier, paths)
        rows = _load(identifier)
        if component_id:
            key = str(UUID(component_id))
            previous = next((r for r in rows if r['id'] == key), None)
            if not previous:
                raise FileNotFoundError('Componente non trovato.')
        else:
            key, previous = str(uuid4()), None
            if len(rows) >= 100:
                raise ValueError('Massimo 100 componenti per workspace.')
        row = {'id': key, 'title': title.strip(), 'kind': kind, 'files': paths, 'file_hashes': hashes,
               'dependencies': dependencies, 'integration': integration.strip(), 'version': previous['version'] + 1 if previous else 1,
               'workspace_digest': workspace_digest(identifier), 'status': 'draft', 'updated_at': now(),
               'history': (previous['history'] if previous else []) + [{'status': 'draft', 'at': now(), 'note': 'Nuova revisione'}]}
        rows = [r for r in rows if r['id'] != key] + [row]
        _save(identifier, rows)
        return describe(identifier, row)


def transition(identifier, component_id, status, note, expected_version, expected_digest):
    """Owner attestation only: integration/activation are recorded, not executed."""
    if status not in {'reviewed', 'integrated', 'active'} or not isinstance(note, str) or not 1 <= len(note.strip()) <= 3000:
        raise ValueError('Stato o nota di revisione non validi.')
    with ws.LOCK:
        rows = _load(identifier)
        row = next((r for r in rows if r['id'] == str(UUID(component_id))), None)
        if not row:
            raise FileNotFoundError('Componente non trovato.')
        value = describe(identifier, row)
        if row['version'] != expected_version or expected_digest != workspace_digest(identifier) or value['stale']:
            raise ws.WorkspaceConflict('Il componente è cambiato: registra una nuova revisione.')
        required_previous = {'reviewed': 'verified', 'integrated': 'reviewed', 'active': 'integrated'}
        if value['status'] != required_previous[status]:
            raise ValueError('Completa verifiche e revisione prima di avanzare lo stato.')
        row['status'] = status
        row['history'].append({'status': status, 'at': now(), 'note': note.strip(), 'source': 'owner_attestation'})
        row['updated_at'] = now()
        _save(identifier, rows)
        return describe(identifier, row)


def deliver(identifier, component_id):
    with ws.LOCK:
        row = next((r for r in listing(identifier) if r['id'] == str(UUID(component_id))), None)
        if not row:
            raise FileNotFoundError('Componente non trovato.')
        if row['stale']:
            raise ws.WorkspaceConflict('Registra una nuova revisione prima della consegna.')
        key = str(uuid4())
        checks = check_history(identifier)
        current = workspace_digest(identifier)
        evidence = [r for r in checks if r.get('workspace_digest') == current]
        manifest = {'id': key, 'created_at': now(), 'workspace_id': identifier,
                    'baseline_digest': ws.manifest(identifier)['source_digest'], 'workspace_digest': current,
                    'component': row, 'checks': evidence, 'activation_performed': False}
        handoff = ('# ' + row['title'] + '\n\nVersione: ' + str(row['version']) + '\nStato: ' + row['status'] +
                   '\n\n## Integrazione\n\n' + row['integration'] + '\n\n## Dipendenze dichiarate\n\n' +
                   ('\n'.join('- ' + d for d in row['dependencies']) or 'Nessuna dichiarata.') +
                   '\n\n## Verifiche mancanti o non superate\n\n' + (', '.join(row['missing_checks']) or 'Nessuna per i profili previsti.') +
                   '\n\nIl pacchetto contiene una bozza da revisionare. Non applica modifiche o attivazioni.\n')
        patch = ''
        contents = {}
        for path in row['files']:
            after = ws.file_path(identifier, path).read_text(encoding='utf-8')
            baseline = ws.file_path(identifier, path, 'baseline')
            before = baseline.read_text(encoding='utf-8') if baseline.exists() else ''
            patch += ''.join(line if line.endswith('\n') else line+'\n\\ No newline at end of file\n' for line in difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/'+path, tofile='b/'+path))
            contents[path] = after
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.writestr('HANDOFF.md', handoff)
            archive.writestr('changes.patch', patch)
            for path, content in contents.items():
                archive.writestr('files/'+path, content)
        folder = ws.directory(identifier) / 'deliveries'
        ws._no_links(folder)
        folder.mkdir(exist_ok=True)
        if len(list(folder.glob('*.zip'))) >= 100:
            raise ValueError('Massimo 100 consegne per workspace.')
        path = folder / (key+'.zip')
        with path.open('xb') as output:
            output.write(memory.getvalue())
        return {'id': key, 'component_id': row['id'], 'version': row['version'], 'status': row['status'],
                'missing_checks': row['missing_checks'], 'download_path': '/api/v1/programmer/workspaces/'+identifier+'/deliveries/'+key,
                'sha256': __import__('hashlib').sha256(memory.getvalue()).hexdigest()}
