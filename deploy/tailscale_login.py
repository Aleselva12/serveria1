"""Configure owner-only Tailscale login on an existing localhost Docker deployment.

Run on the Debian host; the email and generated proxy credential stay in deploy.env.
No containers are restarted by this command. Reuse the printed Compose command.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout


def validate(login, origin, web, serve):
    if not re.fullmatch(r"[A-Za-z0-9.!+_-]+@[A-Za-z0-9.-]+", login):
        raise ValueError('Indirizzo account Tailscale non valido.')
    url = urlsplit(origin)
    if (url.scheme != 'https' or not url.hostname or not url.hostname.endswith('.ts.net')
            or url.port not in {None, 443} or url.username or url.password
            or url.path not in {'', '/'} or url.query or url.fragment):
        raise ValueError('Usa l’origine HTTPS privata *.ts.net, senza percorsi.')
    bindings = web['HostConfig'].get('PortBindings', {}).get('80/tcp') or []
    if len(bindings) != 1 or bindings[0]['HostIp'] != '127.0.0.1':
        raise ValueError('Il servizio web deve pubblicare esclusivamente 127.0.0.1:PORTA:80.')
    gateways = {n['Gateway'] for n in web['NetworkSettings']['Networks'].values() if n.get('Gateway')}
    if len(gateways) != 1:
        raise ValueError('Gateway Docker ambiguo: configurazione manuale necessaria.')
    gateway = str(ipaddress.IPv4Address(gateways.pop()))
    if any(serve.get('AllowFunnel', {}).values()):
        raise ValueError('Disattiva Funnel prima di configurare l’accesso privato.')
    route = serve.get('Web', {}).get(url.hostname + ':443', {}).get('Handlers', {}).get('/', {})
    if route.get('Proxy') != 'http://127.0.0.1:' + bindings[0]['HostPort']:
        raise ValueError('Serve non inoltra questo indirizzo alla porta locale di Cora.')
    return gateway, 'https://' + url.hostname


def update_env(content, changes):
    # Preserve unrelated configuration, including secrets and NAS mounts.
    lines = [line for line in content.splitlines()
             if not any(re.match(r'^\s*(?:export\s+)?' + re.escape(key) + r'\s*=', line)
                        for key in changes)]
    return '\n'.join(lines) + '\n' + ''.join(f'{key}={value}\n' for key, value in changes.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--login', required=True)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--container', default='cora-web-1')
    args = parser.parse_args()
    web = json.loads(run('docker', 'inspect', args.container))[0]
    serve = json.loads(run('tailscale', 'serve', 'status', '--json'))
    gateway, origin = validate(args.login, args.origin, web, serve)
    labels = web['Config']['Labels']
    if Path(labels.get('com.docker.compose.project.working_dir', '')).resolve() != ROOT:
        raise ValueError('Esegui lo script dal checkout usato dal container Cora attivo.')
    config_files = labels.get('com.docker.compose.project.config_files', '').split(',')
    if not config_files or any(not Path(f).is_file() for f in config_files):
        raise ValueError('File Compose originali non disponibili; non posso preservare i mount.')
    env = ROOT / 'deploy.env'
    if env.is_symlink() or not env.is_file():
        raise ValueError('deploy.env assente o non regolare.')
    changes = {'CORA_AUTH_MODE': 'tailscale', 'CORA_TAILSCALE_LOGIN': args.login,
               'CORA_TAILSCALE_PROXY_IP': gateway,
               'CORA_TAILSCALE_PROXY_SECRET': secrets.token_hex(32),
               'CORA_BIND_ADDRESS': '127.0.0.1', 'CORA_UI_ORIGINS': origin,
               'CORA_COOKIE_SECURE': 'true'}
    content = update_env(env.read_text(), changes)
    backup = env.with_name('deploy.env.before-tailscale-' + secrets.token_hex(4))
    with open(backup, 'x', opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
        stream.write(env.read_text())
    descriptor, name = tempfile.mkstemp(prefix='.tailscale-env-', dir=ROOT)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(content)
        base = ['docker', 'compose', '--project-directory', str(ROOT), '--env-file', name,
                '-p', labels['com.docker.compose.project']]
        for file in config_files:
            base += ['-f', file]
        # Validate effective config with all existing overrides before committing.
        effective = json.loads(run(*base, 'config', '--format', 'json'))
        services = effective['services']
        ports = services['web'].get('ports', [])
        if len(ports) != 1 or ports[0].get('host_ip') != '127.0.0.1':
            raise ValueError('Un override Compose espone il web fuori da localhost.')
        if services['api'].get('ports'):
            raise ValueError('Un override pubblica direttamente l’API: rimuovilo prima.')
        for service in ('api', 'web'):
            configured = services[service].get('environment', {})
            for key in ('CORA_AUTH_MODE', 'CORA_TAILSCALE_PROXY_SECRET'):
                if configured.get(key) != changes[key]:
                    raise ValueError('Configurazione autenticazione sovrascritta da Compose.')
        if services['web'].get('environment', {}).get('CORA_TAILSCALE_PROXY_IP') != gateway:
            raise ValueError('IP del proxy sovrascritto da Compose.')
        if services['api'].get('environment', {}).get('CORA_TAILSCALE_LOGIN') != args.login:
            raise ValueError('Identità proprietario sovrascritta da Compose.')
        # Existing owner is retained; no new account/password is silently created.
        result = run(*base, 'exec', '-T', 'api', 'python', '-c',
                     'from core.database import db_connection\n'
                     'with db_connection() as c:\n'
                     ' print(c.execute("SELECT COUNT(*) AS n FROM app_users").fetchone()["n"])')
        if result.strip() != '1':
            raise ValueError('Configura prima un unico proprietario con python -m core.auth.')
        os.replace(name, env)
        base[base.index('--env-file') + 1] = str(env)
        print('Configurazione pronta; backup privato:', backup.name)
        print('Per applicarla, preservando tutti gli override e i mount:')
        print(shlex.join(base + ['up', '-d', '--build', '--wait', 'api', 'web']))
        print('Poi apri dal dispositivo Tailscale:', origin)
        print('Per ripristinare il login precedente: ripristina il backup su deploy.env e riesegui il comando Compose.')
    finally:
        Path(name).unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, subprocess.CalledProcessError) as error:
        # Do not print subprocess output: resolved Compose configs contain secrets.
        raise SystemExit(str(error) if not isinstance(error, subprocess.CalledProcessError)
                         else 'Verifica fallita. Controlla Docker, Tailscale e l’account proprietario sul server.')
