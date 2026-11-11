"""One-time root provisioning for ServerAle; never called by the HTTP API."""
import os
import pwd
import shutil
import subprocess
from pathlib import Path

ROOT=Path('/srv/cora-tools/updater')
USER='ale'
HELPER=Path('/usr/local/lib/cora-host-maintenance.py')
POLICY=Path('/etc/sudoers.d/cora-host-maintenance')
UNITS=Path('/etc/systemd/system')

def run(*args): return subprocess.check_output(args,text=True).strip()

def main():
    if os.geteuid()!=0: raise SystemExit('Eseguire con sudo sul Debian.')
    if run('systemctl','show','cora-updater.service','-p','User','--value')!=USER:
        raise SystemExit('Utente systemd inatteso')
    if run('systemctl','show','cora-updater.service','-p','WorkingDirectory','--value')!=str(ROOT/'installed'):
        raise SystemExit('WorkingDirectory systemd inattesa')
    if (ROOT/'maintenance.enabled').exists(): raise SystemExit('Helper già installato: non sovrascritto.')
    import json
    if any(json.loads(p.read_text()).get('status') in {'queued','running','recovery_required'} for p in (ROOT/'jobs').glob('*.json')):
        raise SystemExit('Completare prima i job updater.')
    print('Installazione helper: arresto temporaneo updater, conservazione copia bootstrap.previous.')
    backup=ROOT/'bootstrap.previous'
    if backup.exists(): raise SystemExit('Backup bootstrap esistente: verificare prima di procedere.')
    source=Path(__file__).resolve().parent
    if source.is_relative_to(ROOT): raise SystemExit('Usare un checkout separato dalla directory updater.')
    account=pwd.getpwnam(USER)
    stage=ROOT/'bootstrap.next'
    if stage.exists(): raise SystemExit('Staging bootstrap esistente: verificare prima di procedere.')
    resources=[HELPER, POLICY, UNITS/'cora-host-maintenance.service', UNITS/'cora-host-maintenance.path']
    if any(p.exists() or p.is_symlink() for p in resources):
        raise SystemExit('Configurazione maintenance già presente: non sovrascritta.')
    shutil.copytree(source,stage/'updater',ignore=shutil.ignore_patterns('__pycache__'))
    for file in (stage/'updater').rglob('*.py'): compile(file.read_bytes(),str(file),'exec')
    for item in [stage,*stage.rglob('*')]: os.chown(item,account.pw_uid,account.pw_gid,follow_symlinks=False)
    switched=False
    try:
        run('systemctl','stop','cora-updater.service')
        if any(json.loads(p.read_text()).get('status') in {'queued','running','recovery_required'} for p in (ROOT/'jobs').glob('*.json')):
            raise RuntimeError('Job iniziato durante la preparazione: bootstrap annullato')
        (ROOT/'installed').rename(backup)
        switched=True
        stage.rename(ROOT/'installed')
        helper=HELPER
        helper.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/'host_maintenance.py',helper);helper.chmod(0o644)
        policy=POLICY
        policy.write_text('ale ALL=(root) NOPASSWD: /usr/bin/systemctl stop cora-updater.service, /usr/bin/systemctl start cora-updater.service\n')
        policy.chmod(0o440);run('visudo','-cf',str(policy))
        units=UNITS
        (units/'cora-host-maintenance.service').write_text('''[Unit]
Description=Cora updater lifecycle helper
After=network.target
[Service]
Type=oneshot
User=ale
UMask=0077
ExecStart=/usr/bin/python3 /usr/local/lib/cora-host-maintenance.py --root /srv/cora-tools/updater
TimeoutStartSec=300
''')
        (units/'cora-host-maintenance.path').write_text('''[Unit]
Description=Watch fixed Cora maintenance request
[Path]
PathExists=/srv/cora-tools/updater/maintenance.request
Unit=cora-host-maintenance.service
[Install]
WantedBy=multi-user.target
''')
        for item in [ROOT/'installed',*(ROOT/'installed').rglob('*')]:
            os.chown(item,account.pw_uid,account.pw_gid,follow_symlinks=False)
        (ROOT/'maintenance.enabled').touch()
        run('systemctl','daemon-reload')
        run('systemctl','start','cora-updater.service')
        from updater.host_maintenance import healthy
        if not healthy(ROOT): raise RuntimeError('Health bootstrap fallito')
        run('systemctl','enable','--now','cora-host-maintenance.path')
    except BaseException:
        run('systemctl','stop','cora-updater.service')
        if switched:
            if (ROOT/'installed').exists(): shutil.rmtree(ROOT/'installed')
            backup.rename(ROOT/'installed')
        subprocess.run(['systemctl','disable','--now','cora-host-maintenance.path'],check=False)
        for resource in resources: resource.unlink(missing_ok=True)
        run('systemctl','daemon-reload')
        (ROOT/'maintenance.enabled').unlink(missing_ok=True)
        run('systemctl','start','cora-updater.service')
        raise
    print('Installazione completata; collaudare dal pulsante Cora.')

if __name__=='__main__': main()
