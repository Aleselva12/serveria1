"""Opt-in private backups on the updater worker, never on a model/tool thread."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import datetime, timezone

from updater.engine import atomic, file_digest


def audit(engine):
    mounts = {}
    for service in ('api','postgres'):
        container = engine.compose('ps','-q',service,timeout=30)
        if not container or '\n' in container: raise ValueError('Serve una sola istanza per servizio.')
        mounts[service] = json.loads(engine.cmd(['docker','inspect','--format={{json .Mounts}}',container],timeout=30))
    states = [m for m in mounts['api'] if m['Destination']=='/state' and m['Type']=='bind']
    if len(states)!=1 or Path(states[0]['Source']).resolve()!=engine.state.resolve():
        raise ValueError('Mount /state diverso dalla configurazione updater.')
    if not any(m['Destination']=='/var/lib/postgresql/data' for m in mounts['postgres']):
        raise ValueError('Volume PostgreSQL non riconosciuto.')
    evidence = {'mounts':mounts,'compose_sha256':file_digest(engine.root/'compose.json'),
                'state_root':str(engine.state.resolve())}
    evidence['audit_sha256'] = hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest()
    evidence['excluded'] = [m['Destination'] for m in mounts['api'] if m['Destination']!='/state']
    return evidence


def private_root(engine, settings):
    raw=Path(settings['destination']).expanduser()
    if not raw.is_absolute() or raw.is_symlink(): raise ValueError('Destinazione assoluta privata richiesta.')
    root=raw.resolve()
    if any((parent/'.git').exists() for parent in (root,*root.parents)):
        raise ValueError('Destinazione backup dentro un checkout Git.')
    for protected in (engine.state.resolve(),engine.root.resolve()):
        if root==protected or root.is_relative_to(protected) or protected.is_relative_to(root):
            raise ValueError('Backup fuori da state, updater e dai loro antenati.')
    if any(p.is_symlink() for p in (raw,*raw.parents)): raise ValueError('Link nella destinazione backup.')
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if os.name=='posix' and (root.stat().st_uid!=os.getuid() or root.stat().st_mode & 0o077):
        raise ValueError('Destinazione deve appartenere al servizio con permessi 0700.')
    return root


def verify_encrypted(folder):
    if folder.is_symlink(): raise ValueError('Link backup non consentito.')
    manifest=json.loads((folder/'complete.json').read_text())
    encrypted=folder/'data.tar.age'
    if encrypted.is_symlink() or file_digest(encrypted)!=manifest['sha256']:
        raise ValueError('Backup cifrato danneggiato.')
    return manifest


def prune(root, keep):
    if not 2<=keep<=365: raise ValueError('Retention ammessa: 2..365 snapshot.')
    valid=[]
    for folder in sorted(root.glob('cora-*'),reverse=True):
        if not folder.is_dir() or folder.is_symlink(): continue
        try: verify_encrypted(folder)
        except (OSError,ValueError,KeyError): continue
        valid.append(folder)
    for folder in valid[keep:]: shutil.rmtree(folder)


def create(engine, settings):
    evidence=audit(engine)
    if evidence['audit_sha256']!=settings.get('audit_sha256'):
        raise ValueError('Audit volumi mancante o cambiato; rinnova audit prima del backup.')
    root=private_root(engine,settings)
    keep=int(settings.get('keep',7))
    if not 2<=keep<=365: raise ValueError('Retention ammessa: 2..365 snapshot.')
    recipient=settings['age_recipient']
    if not recipient.startswith('age1') or len(recipient)>150: raise ValueError('Destinatario age pubblico richiesto.')
    if not shutil.which('age'): raise ValueError('Installare age sul server prima di abilitare i backup.')
    folder=root/('cora-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+os.urandom(4).hex())
    folder.mkdir(mode=0o700)
    images=engine.images()
    # Persist the exact restart images before stopping anything. On crash tick recovers only services.
    marker=engine.root/'data-backup-pending.json'
    atomic(marker,{'images':images})
    try:
        engine.compose('stop','-t','330','web','api',timeout=400)
        with tempfile.TemporaryDirectory(prefix='.staging-',dir=root) as temporary:
            stage=Path(temporary)
            with (stage/'database.dump').open('wb') as output:
                engine.compose('exec','-T','postgres','sh','-c','exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc',stdout=output)
            with (stage/'database.dump').open('rb') as source:
                engine.compose('exec','-T','postgres','pg_restore','--list',stdin=source)
            with (stage/'state.tar.gz').open('wb') as output:
                engine.compose('run','--rm','--no-deps','-T','--entrypoint','tar','api','czf','-','-C','/state','.',stdout=output)
            # Fully resolved Compose contains credentials and replaces deploy.env for updater installs.
            for name in ('compose.json','config.json','current.json','bridge.token'):
                shutil.copyfile(engine.root/name,stage/name)
                (stage/name).chmod(0o600)
            with tarfile.open(stage/'private-files.tar.gz','w:gz') as extra:
                for index,filename in enumerate(settings.get('private_files',[])):
                    path=Path(filename)
                    if not path.is_absolute() or path.is_symlink() or not path.is_file():
                        raise ValueError('File privato aggiuntivo non regolare.')
                    extra.add(path,arcname=str(index)+'-'+path.name,recursive=False)
            manifest={'version':2,'created_at':datetime.now(timezone.utc).isoformat(),'images':images,
                      'audit':evidence,'sha256':{p.name:file_digest(p) for p in stage.iterdir()}}
            atomic(stage/'manifest.json',manifest)
            with tempfile.TemporaryFile(dir=root) as archive:
                with tarfile.open(fileobj=archive,mode='w') as tar:
                    for path in stage.iterdir(): tar.add(path,arcname=path.name,recursive=False)
                archive.seek(0)
                with (folder/'data.tar.age').open('xb') as output:
                    os.chmod(output.name,0o600)
                    subprocess.run(['age','--encrypt','--recipient',recipient],stdin=archive,stdout=output,stderr=subprocess.DEVNULL,check=True,timeout=7200)
        atomic(folder/'complete.json',{'version':2,'sha256':file_digest(folder/'data.tar.age')})
        verify_encrypted(folder)
    finally:
        engine.compose('up','-d','--no-build','--pull','never','--wait','--wait-timeout','180','api','web',images=images,timeout=550)
        marker.unlink(missing_ok=True)
    # Prune only after success and healthy restart, never updater release/rollback backups.
    prune(root,keep)
    return folder


def recover_pending(engine):
    pending=engine.root/'data-backup-pending.json'
    if pending.exists():
        images=json.loads(pending.read_text())['images']
        engine.compose('up','-d','--no-build','--pull','never','--wait','--wait-timeout','180','api','web',images=images,timeout=550)
        pending.unlink()
        atomic(engine.root/'data-backup-status.json',{'attempted_at':time.time(),'status':'interrupted_services_recovered'})


def tick(engine):
    """Called only while holding engine.lock and with no queued/running/recovery job."""
    recover_pending(engine)
    settings=engine.config.get('data_backups',{})
    if not settings.get('enabled'): return
    status=engine.root/'data-backup-status.json'
    previous=json.loads(status.read_text()) if status.exists() else {}
    interval=max(3600,int(settings.get('interval_seconds',86400)))
    if time.time()-previous.get('attempted_at',0)<interval: return
    state={'attempted_at':time.time(),'status':'running'}
    atomic(status,state)
    try:
        create(engine,settings)
        state.update(status='completed',completed_at=time.time())
    except Exception as error:
        state.update(status='failed',error_type=type(error).__name__)
    atomic(status,state)
    if (engine.root/'data-backup-pending.json').exists(): raise RuntimeError('Backup: riavvio servizi non confermato; recovery necessaria.')


def unpack(folder, destination, identity):
    """Decrypt/verify into a NEW private directory. Never restores into live state/DB."""
    verify_encrypted(folder)
    destination.mkdir(mode=0o700,parents=False,exist_ok=False)
    with tempfile.TemporaryFile(dir=destination) as stream:
        subprocess.run(['age','--decrypt','--identity',str(identity),str(folder/'data.tar.age')],stdout=stream,stderr=subprocess.DEVNULL,check=True,timeout=7200)
        stream.seek(0)
        with tarfile.open(fileobj=stream,mode='r:') as archive:
            members=archive.getmembers()
            expected={'manifest.json','database.dump','state.tar.gz','private-files.tar.gz','compose.json','config.json','current.json','bridge.token'}
            if len(members)!=len(expected) or {m.name for m in members}!=expected or any(not m.isfile() for m in members):
                raise ValueError('Archivio non valido.')
            for member in members:
                with archive.extractfile(member) as source, (destination/member.name).open('xb') as output:
                    os.chmod(output.name,0o600);shutil.copyfileobj(source,output)
    manifest=json.loads((destination/'manifest.json').read_text())
    if manifest.get('version')!=2 or set(manifest['sha256'])!=expected-{'manifest.json'}:
        raise ValueError('Manifest non valido.')
    for name,digest in manifest['sha256'].items():
        if file_digest(destination/name)!=digest: raise ValueError('Checksum interno non valido.')
    # Validate the nested state tar before any operator attempts restoration.
    with tarfile.open(destination/'state.tar.gz') as archive:
        for member in archive:
            path=Path(member.name)
            if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                raise ValueError('State contiene link o elementi speciali: serve recupero manuale isolato.')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('audit','unpack'))
    parser.add_argument('--root',type=Path)
    parser.add_argument('--snapshot',type=Path)
    parser.add_argument('--destination',type=Path)
    parser.add_argument('--identity',type=Path)
    args=parser.parse_args()
    if args.command=='audit':
        if not args.root: parser.error('--root richiesto')
        from updater.engine import Engine
        print(json.dumps(audit(Engine(args.root.resolve())),indent=2))
    else:
        if not all((args.snapshot,args.destination,args.identity)):parser.error('--snapshot --destination --identity richiesti')
        unpack(args.snapshot,args.destination,args.identity)
        print('Decifrato e verificato su destinazione nuova. Nessun dato attivo modificato.')


if __name__=='__main__':main()
