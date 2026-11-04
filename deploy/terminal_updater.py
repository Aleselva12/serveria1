"""Install the optional terminal in the updater's persistent Compose snapshot.

The operator must stop or suspend the updater while changing its snapshot.
API/web images and all existing service settings are left untouched.
"""
import copy
import json
import os
from pathlib import Path
import secrets
import shlex
import tempfile

from deploy.tailscale_login import run, update_env, validate


def add_terminal(snapshot, service):
    candidate = copy.deepcopy(snapshot)
    if 'terminal' in candidate['services']:
        raise ValueError('Terminale già configurato: nessuna configurazione sovrascritta.')
    if service.get('ports') or service.get('privileged') or service.get('network_mode') == 'host':
        raise ValueError('Configurazione terminale non privata.')
    service = copy.deepcopy(service)
    service.pop('build', None)
    candidate['services']['terminal'] = service
    return candidate


def host_key():
    from deploy.terminal_setup import known_host_line
    return known_host_line(Path('/etc/ssh/ssh_host_ed25519_key.pub').read_text())


def prepare(args, source):
    root = args.updater_root.absolute()
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):
        raise ValueError('Percorso updater non valido.')
    file = root / 'compose.json'
    images = root / 'images.json'
    if any(p.is_symlink() or not p.is_file() for p in (file, images)):
        raise ValueError('Snapshot e immagini updater non disponibili.')
    original = file.read_bytes()
    image_bytes = images.read_bytes()
    snapshot = json.loads(original)
    web = json.loads(run('docker', 'inspect', args.container))[0]
    labels = web['Config']['Labels']
    files = labels.get('com.docker.compose.project.config_files', '').split(',')
    if [Path(p).resolve() for p in files] != [file.resolve(), images.resolve()]:
        raise ValueError('Lo snapshot indicato non appartiene al container attivo.')
    for path in (root / 'jobs').glob('*/job.json'):
        if json.loads(path.read_text()).get('status') in {'queued', 'running', 'recovery_required'}:
            raise ValueError('Job updater in corso o da recuperare.')
    config = snapshot['services']['api']['environment']
    web_env = snapshot['services']['web']['environment']
    origins = config.get('CORA_UI_ORIGINS', '').split(',')
    if config.get('CORA_AUTH_MODE') != 'tailscale' or len(origins) != 1:
        raise ValueError('Configura una sola origine HTTPS con login Tailscale.')
    gateway, origin = validate(config.get('CORA_TAILSCALE_LOGIN', ''), origins[0].strip(),
                               web, json.loads(run('tailscale', 'serve', 'status', '--json')))
    if (web_env.get('CORA_AUTH_MODE') != 'tailscale'
            or web_env.get('CORA_TAILSCALE_PROXY_IP') != gateway
            or len(config.get('CORA_TAILSCALE_PROXY_SECRET', '')) < 32
            or web_env.get('CORA_TAILSCALE_PROXY_SECRET') != config['CORA_TAILSCALE_PROXY_SECRET']):
        raise ValueError('Configurazione proxy Tailscale incoerente.')
    folder = args.config_root.absolute()
    if folder.is_symlink() or any(p.is_symlink() for p in folder.parents):
        raise ValueError('Percorso chiave host non valido.')
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o755)
    known = folder / 'known_hosts'
    if known.is_symlink():
        raise ValueError('known_hosts non può essere un link simbolico.')
    key = host_key()
    if known.exists() and known.read_text() != key:
        raise ValueError('Chiave host cambiata: verificare prima di sostituirla.')
    known.write_text(key)
    known.chmod(0o644)
    settings = {k: config[k] for k in ('CORA_AUTH_MODE', 'CORA_TAILSCALE_LOGIN', 'CORA_TAILSCALE_PROXY_SECRET')}
    settings.update(CORA_TERMINAL_USER=args.user, CORA_TERMINAL_ORIGIN=origin,
                    CORA_TERMINAL_CONFIG_ROOT=str(folder))
    project = labels['com.docker.compose.project']
    base = ['docker', 'compose', '-p', project, '-f', str(file), '-f', str(images)]
    with tempfile.TemporaryDirectory(prefix='.terminal-', dir=root) as temporary:
        temporary = Path(temporary)
        env = temporary / 'terminal.env'
        env.write_text(update_env('', settings))
        env.chmod(0o600)
        resolved = json.loads(run('docker', 'compose', '--project-directory', str(source),
                                  '--env-file', str(env), '-p', project,
                                  '-f', str(source / 'compose.terminal.yml'), 'config', '--format', 'json'))
        candidate = add_terminal(snapshot, resolved['services']['terminal'])
        pending = temporary / 'compose.json'
        pending.write_text(json.dumps(candidate, indent=2))
        pending.chmod(0o600)
        run('docker', 'compose', '-p', project, '-f', str(pending), '-f', str(images), 'config', '--quiet')
        if file.read_bytes() != original or images.read_bytes() != image_bytes:
            raise ValueError('Configurazione cambiata durante il setup: ripetere a updater fermo.')
        backup = root / ('compose.before-terminal-' + secrets.token_hex(8) + '.json')
        with open(backup, 'xb', opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, file)
    print('Terminale aggiunto allo snapshot persistente. Backup: ' + str(backup))
    print(shlex.join(['docker', 'build', '--target', 'terminal', '-t', 'cora-terminal:local', str(source)]))
    print(shlex.join(base + ['up', '-d', '--no-build', '--no-deps', 'terminal']))
    print('Riattiva l’updater. API/web e immagini attive non sono stati modificati.')
