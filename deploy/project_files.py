"""Persist the opt-in project mount in an already installed host updater."""
import argparse
import json
from pathlib import Path
import tempfile
import os
import uuid


def configure(updater_root, project_root):
    root = Path(updater_root).resolve()
    project = Path(project_root).resolve()
    if not (project / 'compose.yml').is_file():
        raise ValueError('Cartella progetto non valida.')
    path = root / 'compose.json'
    original = path.read_bytes()
    config = json.loads(original)
    api = config['services']['api']
    # Preserve all other frozen host settings, credentials and image choices.
    env = api.setdefault('environment', {})
    resources = json.loads(env.get('CORA_FILE_ROOTS') or '[]')
    resources = [r for r in resources if r['id'] != 'project']
    resources.append({'id': 'project', 'label': 'Progetto Cora', 'path': '/project', 'writable': True})
    env['CORA_FILE_ROOTS'] = json.dumps(resources)
    mounts = api.setdefault('volumes', [])
    mounts[:] = [m for m in mounts if m.get('target') != '/project']
    mounts.append({'type': 'bind', 'source': str(project), 'target': '/project',
                   'read_only': False, 'bind': {'create_host_path': False}})
    backup = root / ('compose.before-project-' + uuid.uuid4().hex + '.json')
    with backup.open('xb') as stream:
        os.chmod(backup, 0o600)
        stream.write(original)
    fd, name = tempfile.mkstemp(dir=root)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(config, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--updater-root', default='/srv/cora-updater')
    parser.add_argument('--project-root', default='.')
    args = parser.parse_args()
    backup = configure(args.updater_root, args.project_root)
    print('Configurazione aggiornata. Backup:', backup)
    print('Riavvia il servizio updater per caricare il mount persistente.')


if __name__ == '__main__':
    main()
