"""Prepare the personal SSH terminal on the Debian host, preserving Compose overrides."""
import argparse
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shlex
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deploy.tailscale_login import run, update_env, validate


def known_host_line(public_key):
    fields = public_key.split()
    if len(fields) < 2 or fields[0] != 'ssh-ed25519' or not re.fullmatch(r'[A-Za-z0-9+/=]+', fields[1]):
        raise ValueError('Chiave pubblica SSH Ed25519 non valida.')
    return 'host.docker.internal ' + ' '.join(fields[:2]) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', required=True, help='Utente Debian esistente, diverso da root')
    parser.add_argument('--container', default='cora-web-1')
    parser.add_argument('--config-root', type=Path, default=Path('/srv/cora-tools/terminal'))
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', args.user) or pwd.getpwnam(args.user).pw_uid == 0:
        raise ValueError('Scegli un utente Debian esistente, non root.')
    env = ROOT/'deploy.env'
    if env.is_symlink() or not env.is_file():
        raise ValueError('deploy.env assente o non regolare.')
    web = json.loads(run('docker', 'inspect', args.container))[0]
    labels = web['Config']['Labels']
    if Path(labels.get('com.docker.compose.project.working_dir', '')).resolve() != ROOT:
        raise ValueError('Esegui dal checkout usato dal container Cora attivo.')
    files = labels.get('com.docker.compose.project.config_files', '').split(',')
    if not files or any(not Path(file).is_file() for file in files):
        raise ValueError('File Compose originali non disponibili.')
    base = ['docker', 'compose', '--project-directory', str(ROOT), '--env-file', str(env),
            '-p', labels['com.docker.compose.project']]
    for file in files:
        base += ['-f', file]
    effective = json.loads(run(*base, 'config', '--format', 'json'))
    config = effective['services']['api']['environment']
    if config.get('CORA_AUTH_MODE') != 'tailscale':
        raise ValueError('Configura prima l’accesso proprietario Tailscale (deploy/tailscale_login.py).')
    origins = config.get('CORA_UI_ORIGINS', '').split(',')
    if len(origins) != 1:
        raise ValueError('Configura una sola origine HTTPS Tailscale in CORA_UI_ORIGINS.')
    gateway, origin = validate(config.get('CORA_TAILSCALE_LOGIN', ''), origins[0].strip(), web,
                               json.loads(run('tailscale', 'serve', 'status', '--json')))
    web_env = effective['services']['web']['environment']
    if (web_env.get('CORA_TAILSCALE_PROXY_IP') != gateway
            or len(config.get('CORA_TAILSCALE_PROXY_SECRET', '')) < 32
            or web_env.get('CORA_TAILSCALE_PROXY_SECRET') != config['CORA_TAILSCALE_PROXY_SECRET']):
        raise ValueError('Configurazione del proxy Tailscale incoerente.')
    # Trust the host key read locally, never an unauthenticated ssh-keyscan response.
    key = known_host_line(Path('/etc/ssh/ssh_host_ed25519_key.pub').read_text())
    folder = args.config_root.absolute()
    if folder.is_symlink() or any(p.is_symlink() for p in folder.parents):
        raise ValueError('La directory di configurazione non può attraversare link simbolici.')
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o755)  # Contains only the PUBLIC host key.
    known = folder/'known_hosts'
    if known.is_symlink():
        raise ValueError('known_hosts non può essere un link simbolico.')
    known.write_text(key);known.chmod(0o644)
    changes = {'CORA_TERMINAL_USER': args.user, 'CORA_TERMINAL_ORIGIN': origin,
               'CORA_TERMINAL_CONFIG_ROOT': str(folder)}
    content = update_env(env.read_text(), changes)
    backup = env.with_name('deploy.env.before-terminal-' + secrets.token_hex(4))
    with open(backup, 'x', opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
        stream.write(env.read_text())
    descriptor, name = tempfile.mkstemp(prefix='.terminal-env-', dir=ROOT)
    try:
        with os.fdopen(descriptor, 'w') as stream: stream.write(content)
        base[base.index('--env-file')+1] = name
        overlay = str(ROOT/'compose.terminal.yml')
        if overlay not in files: base += ['-f', overlay]
        candidate = json.loads(run(*base, 'config', '--format', 'json'))
        service = candidate['services']['terminal']
        if service.get('ports') or service.get('privileged') or service.get('network_mode') == 'host':
            raise ValueError('Un override espone il servizio terminale o gli dà privilegi host.')
        expected = {**changes, 'CORA_AUTH_MODE': 'tailscale', 'CORA_TAILSCALE_LOGIN': config['CORA_TAILSCALE_LOGIN'],
                    'CORA_TAILSCALE_PROXY_SECRET': config['CORA_TAILSCALE_PROXY_SECRET']}
        for key, value in expected.items():
            if key != 'CORA_TERMINAL_CONFIG_ROOT' and service['environment'].get(key) != value:
                raise ValueError('Configurazione terminale sovrascritta: ' + key)
        os.replace(name, env)
        base[base.index('--env-file')+1] = str(env)
        print('Terminale predisposto. Le password Debian restano gestite da SSH.')
        print('Applica con questo comando (preserva i mount e gli override esistenti):')
        print(shlex.join(base + ['up', '-d', '--build', 'terminal', 'web']))
        print('Apri Programma → Terminale del server da ' + origin)
    finally:
        if Path(name).exists(): Path(name).unlink()


if __name__ == '__main__':
    main()
