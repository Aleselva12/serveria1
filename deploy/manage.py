"""Debian host operations. No secrets are passed as command-line arguments."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'deploy.env'
COMPOSE_FILES = ()
DIRECTORIES = ('chat_attachments','knowledge','library_originals','audio/_transcripts','quotes','logs','models',
               'chat-transcripts','structure_workspace','automation_drafts','gmail','files')


def compose(*args, **kwargs):
    files = [ROOT/'compose.yml', *COMPOSE_FILES]
    options = [part for path in files for part in ('-f', str(path))]
    return subprocess.run(['docker','compose','--env-file',str(ENV),*options,*args],
                          cwd=ROOT,check=True,**kwargs)


def init():
    if ENV.exists(): raise ValueError('deploy.env esiste già: non viene sovrascritto.')
    uid = os.getuid() or 1000
    gid = os.getgid() or 1000
    template = (ROOT/'deploy/deploy.env.example').read_text()
    template = template.replace('GENERATED_BY_INIT',secrets.token_hex(32))
    template = template.replace('CORA_UID=1000',f'CORA_UID={uid}').replace('CORA_GID=1000',f'CORA_GID={gid}')
    state = ROOT/'state'
    if state.exists() and any(state.iterdir()): raise ValueError('state non vuota: prepara esplicitamente i mount esistenti.')
    state.mkdir(exist_ok=True)
    for directory in DIRECTORIES: (state/directory).mkdir(parents=True,exist_ok=True)
    if os.getuid()==0:
        for directory in [state,*state.rglob('*')]: os.chown(directory,uid,gid)
    descriptor=os.open(ENV,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as stream: stream.write(template)
    print('Configurazione creata. Controlla origine browser e URL Ollama prima di avviare.')


def digest(path):
    hasher=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):hasher.update(chunk)
    return hasher.hexdigest()


def check_backup(path):
    manifest=json.loads((path/'manifest.json').read_text())
    if manifest.get('version')!=1:raise ValueError('Formato backup non supportato.')
    expected={'database.dump','state.tar.gz','deploy.env'}
    if set(manifest['sha256'])!=expected:raise ValueError('Manifest incompleto.')
    for name in expected:
        if digest(path/name)!=manifest['sha256'][name]:raise ValueError('Backup danneggiato: '+name)
    return manifest


def backup(path):
    # Stop every Cora writer before either snapshot. External NAS mounts are excluded.
    path.mkdir(parents=True,exist_ok=False);path.chmod(0o700)
    compose('stop','web','api')
    try:
        with (path/'database.dump').open('wb') as stream:
            compose('exec','-T','postgres','sh','-c','exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc',stdout=stream)
        with (path/'state.tar.gz').open('wb') as stream:
            compose('run','--rm','--no-deps','-T','--entrypoint','tar','api','czf','-','-C','/state','.',stdout=stream)
        shutil.copyfile(ENV,path/'deploy.env');(path/'deploy.env').chmod(0o600)
        revision=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,capture_output=True)
        images=compose('images','--format','json',capture_output=True,text=True).stdout
        manifest={'version':1,'created_at':datetime.now(timezone.utc).isoformat(),
                  'revision':revision.stdout.strip(),'images':images,
                  'sha256':{name:digest(path/name) for name in ('database.dump','state.tar.gz','deploy.env')}}
        (path/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    except BaseException:
        print('Backup incompleto; Cora resta ferma. Verifica prima di riavviare.',file=sys.stderr)
        raise
    compose('up','-d','--wait','api','web')
    print('Backup verificabile creato:',path)


def restore(path):
    check_backup(path)
    # Restore is intentionally limited to a fresh target, never overwrites live data.
    compose('stop','web','api')
    compose('up','-d','--wait','postgres')
    sql="SELECT COUNT(*) FROM pg_tables WHERE schemaname='public'"
    result=compose('exec','-T','postgres','psql','-U','cora','-d','cora','-Atc',sql,capture_output=True,text=True)
    if result.stdout.strip()!='0':raise ValueError('Ripristino consentito soltanto in un database vuoto.')
    result=compose('run','--rm','--no-deps','-T','--entrypoint','sh','api','-c',
                   'find /state -type f -o -type l',capture_output=True,text=True)
    if result.stdout.strip():raise ValueError('Ripristino consentito soltanto in state vuota.')
    with (path/'database.dump').open('rb') as stream:
        compose('exec','-T','postgres','pg_restore','-U','cora','-d','cora','--exit-on-error','--no-owner','--no-privileges',stdin=stream)
    with (path/'state.tar.gz').open('rb') as stream:
        compose('run','--rm','--no-deps','-T','--entrypoint','tar','api','xzf','-','--no-same-owner','-C','/state',stdin=stream)
    compose('exec','-T','postgres','psql','-U','cora','-d','cora','-c','DELETE FROM app_sessions')
    print('Dati ripristinati, sessioni revocate. Controlla deploy.env del nuovo host, poi esegui up.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('init','check','up','owner','backup','verify-backup','restore','audio-model','audio-check','doctor'))
    parser.add_argument('path',nargs='?',type=Path)
    parser.add_argument('--revision',help='Immutable model revision; defaults to resolving the current public revision once')
    parser.add_argument('--compose-file', action='append', default=[], type=Path,
                        help='Additional Compose override; repeat in order for every operation')
    args=parser.parse_args()
    global COMPOSE_FILES
    COMPOSE_FILES = tuple((path if path.is_absolute() else ROOT/path).resolve() for path in args.compose_file)
    for path in COMPOSE_FILES:
        if not path.is_file():parser.error('Compose file non trovato: '+str(path))
    if args.command=='init':return init()
    if args.command in {'backup','restore','verify-backup'}:
        if args.path is None:parser.error('Specificare la cartella backup.')
        path=args.path.resolve()
        if args.command=='verify-backup':check_backup(path);print('Checksum backup: OK');return
        if not ENV.exists():raise ValueError('Preparare deploy.env sul target prima di continuare.')
        return backup(path) if args.command=='backup' else restore(path)
    if not ENV.exists():raise ValueError('Esegui prima init.')
    if args.command=='check':compose('config','--quiet')
    elif args.command=='up':compose('up','-d','--build','--wait')
    elif args.command=='owner':compose('exec','api','python','-m','core.auth','--ensure-owner')
    elif args.command=='audio-model':
        model=str(args.path) if args.path else 'small'
        command=['run','--rm','--no-deps','-T','-e','HF_HUB_OFFLINE=0','api','python','-m','audio_agent.model_setup','--model',model]
        if args.revision:command+=['--revision',args.revision]
        compose(*command)
    elif args.command=='audio-check':compose('run','--rm','--no-deps','-T','api','python','-m','audio_agent.model_setup','--check')
    elif args.command=='doctor':compose('exec','-T','api','python','-m','deploy.doctor')


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.CalledProcessError) as error:
        print('Operazione non riuscita:',error,file=sys.stderr);raise SystemExit(1)

