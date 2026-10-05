"""Host-side Git and release engine. Installed separately from mutable Cora code."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tarfile
import threading
from datetime import datetime, timezone
from uuid import UUID, uuid4

BUSY = {'queued', 'running'}
MAX_FILE, MAX_TOTAL = 1_000_000, 40_000_000


def now(): return datetime.now(timezone.utc).isoformat()
def sha(value): return hashlib.sha256(value).hexdigest()


def file_digest(path):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def atomic(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.flush(); os.fsync(output.fileno())
    os.replace(temporary, path)


def source_name(name):
    parts = Path(name).parts
    if any(p.lower().startswith('.env') and p.lower()!='.env.example' for p in parts):raise ValueError('File ambiente privato non consentito.')
    if not name or Path(name).is_absolute() or any(p in {'..', '.git', '.env', 'deploy.env', 'state', 'data', 'backups', 'node_modules', '__pycache__'} for p in parts):
        raise ValueError('Percorso sorgente non consentito.')
    if Path(name).suffix == '.json' and any(word in Path(name).name.lower() for word in ('credential', 'secret', 'token')):
        raise ValueError('Credenziali non ammesse nel sorgente del rilascio.')
    return name


class Engine:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.config = json.loads((self.root/'config.json').read_text())
        self.repo = self.root/'repo.git'
        self.state = Path(self.config['state_root'])
        self.workspaces = self.state/'programmer'
        self.jobs = self.root/'jobs'; self.jobs.mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self.wakeup = threading.Event()
        self.closed = threading.Event()
        self.worker = None

    def cmd(self, arguments, *, cwd=None, stdin=None, stdout=None, timeout=1200):
        with __import__('tempfile').TemporaryFile() as log:
            process = subprocess.run(arguments, cwd=cwd, stdin=stdin, stdout=stdout or log, stderr=log,
                                     timeout=timeout, check=False, shell=False)
            size=log.seek(0,2);log.seek(max(0,size-12000));text=log.read(12000).decode(errors='replace')
        if process.returncode:
            (self.root/'last-error.log').write_text(text)
            (self.root/'last-error.log').chmod(0o600)
            # Command output may contain database values or interpolated configuration.
            raise RuntimeError('Comando '+Path(arguments[0]).name+' non riuscito (codice '+str(process.returncode)+').')
        return text.strip()

    def git(self, *args, cwd=None):
        common = ['git', '-c', 'core.sshCommand=ssh -oBatchMode=yes', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgSign=false', '-c', 'user.name=Cora owner', '-c', 'user.email=cora@localhost']
        return self.cmd(common + ([] if cwd else ['--git-dir='+str(self.repo)]) + list(args), cwd=cwd, timeout=60)

    def compose(self, *args, images=None, stdin=None, stdout=None, timeout=1200):
        flags = ['docker', 'compose', '-p', self.config['project'], '-f', str(self.root/'compose.json')]
        if images:
            file = self.root/'images.json'
            atomic(file, {'services': {name: {'image': image} for name,image in images.items()}})
            flags += ['-f', str(file)]
        return self.cmd(flags+list(args), stdin=stdin, stdout=stdout, timeout=timeout)

    def current(self): return json.loads((self.root/'current.json').read_text())
    def path(self, key): return self.jobs/str(UUID(key))
    def load(self, key): return json.loads((self.path(key)/'job.json').read_text())
    def save(self, row):
        row['updated_at'] = now(); atomic(self.path(row['id'])/'job.json', row)
    def public(self, row):
        keys = ('id','workspace_id','kind','status','phase','commit','base_commit','created_at','updated_at','error','checks','rollback','backup_valid','previous_commit','branch','compare_url')
        return {key: row[key] for key in keys if key in row}
    def list_jobs(self):
        return sorted([self.public(json.loads(p.read_text())) for p in self.jobs.glob('*/job.json')], key=lambda r:r['created_at'], reverse=True)[:100]
    def phase(self, row, value): row['phase']=value; self.save(row)

    def workspace(self, key):
        path = self.workspaces/str(UUID(key))
        if path.is_symlink(): raise ValueError('Workspace non valido.')
        manifest = json.loads((path/'manifest.json').read_text())
        if manifest.get('mode') != 'git': raise ValueError('Crea un workspace Git per preparare un rilascio.')
        return path, manifest

    def scan(self, files):
        result = {}
        for folder, dirs, names in os.walk(files, followlinks=False):
            dirs[:] = [d for d in dirs if d != '.git']
            for name in dirs+names:
                if (Path(folder)/name).is_symlink(): raise ValueError('Link non ammesso nel progetto.')
            for name in names:
                if name == '.git' and Path(folder) == files: continue
                path = Path(folder)/name; relative = source_name(path.relative_to(files).as_posix())
                if path.stat().st_size > MAX_FILE: raise ValueError('File oltre 1 MB: '+relative)
                data = path.read_bytes(); data.decode('utf-8')
                result[relative] = sha(data)
        if len(result)>6000 or sum((files/p).stat().st_size for p in result)>MAX_TOTAL:
            raise ValueError('Sorgenti oltre il limite (6000 file / 40 MB).')
        return dict(sorted(result.items()))

    def remote(self):
        """The destination is provisioned by the owner, never supplied by the model."""
        repo=self.config.get('github_repository','')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):
            raise ValueError('Repository GitHub non configurata sul servizio host.')
        return 'git@github.com:'+repo+'.git'

    def fetch_source(self):
        base=self.current()['commit']
        if not self.config.get('github_repository'):return base
        branch=self.config.get('github_branch','main')
        self.git('check-ref-format','refs/heads/'+branch)
        self.git('fetch','--no-tags',self.remote(),'+refs/heads/'+branch+':refs/remotes/github/base')
        upstream=self.git('rev-parse','refs/remotes/github/base')
        common=self.git('merge-base',base,upstream)
        if common==base:return upstream
        if common==upstream:return base
        raise ValueError('GitHub e versione attiva divergono. Integra il branch Cora su GitHub prima di creare un nuovo workspace.')

    def publish(self, row):
        self.phase(row,'publishing')
        branch='cora/'+row['workspace_id']
        # No force push: concurrent changes on GitHub cause a failure, never data loss.
        self.git('push',self.remote(),row['commit']+':refs/heads/'+branch)
        remote=self.git('ls-remote',self.remote(),'refs/heads/'+branch).split()
        if not remote or remote[0]!=row['commit']:raise ValueError('Commit remoto diverso: verificare GitHub.')
        from urllib.parse import quote
        row['branch']=branch
        row['compare_url']='https://github.com/'+self.config['github_repository']+'/compare/'+quote(self.config.get('github_branch','main'),safe='')+'...'+quote(branch,safe='')+'?expand=1'
        row['status']='completed';self.phase(row,'completed')

    def create_workspace(self, title):
        if not 1<=len(title.strip())<=120: raise ValueError('Titolo non valido.')
        with self.lock:
            if any(j['status'] in BUSY | {'recovery_required'} for j in self.list_jobs()):raise ValueError('Attendi il job di aggiornamento in corso.')
            source=self.fetch_source()
            key=str(uuid4()); path=self.workspaces/key; path.mkdir(parents=True)
            base=self.current()['commit']
            self.git('worktree','add','-b','cora/'+key,str(path/'files'),source)
            try:
                hashes=self.scan(path/'files')
                for relative in hashes:
                    destination=path/'baseline'/relative; destination.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(path/'files'/relative,destination)
                manifest={'id':key,'title':title.strip(),'created_at':now(),'status':'draft','mode':'git','base_commit':base,'source_commit':source,
                          'baseline':hashes,'file_count':len(hashes),'source_digest':sha(json.dumps(list(hashes.items())).encode())}
                atomic(path/'manifest.json',manifest)
                if os.getuid()==0:
                    for item in [path,*path.rglob('*')]:os.chown(item,self.config['uid'],self.config['gid'],follow_symlinks=False)
                return {k:v for k,v in manifest.items() if k!='baseline'}
            except BaseException:
                self.git('worktree','remove','--force',str(path/'files')); shutil.rmtree(path); raise

    def commit_workspace(self, key, message):
        if not 1<=len(message.strip())<=200: raise ValueError('Messaggio commit non valido.')
        with self.lock:
            path,manifest=self.workspace(key); hashes=self.scan(path/'files')
            if any(j['status'] in BUSY | {'recovery_required'} for j in self.list_jobs()): raise ValueError('Attendi il job di aggiornamento in corso.')
            # Force tracked input even if generated .gitignore would hide a file.
            self.git('add','--force','--all',cwd=path/'files')
            if self.git('diff','--cached','--name-only',cwd=path/'files'):
                self.git('commit','-m',message,cwd=path/'files')
            commit=self.git('rev-parse','HEAD',cwd=path/'files')
            manifest['commit']=commit; manifest['committed_files']=hashes
            atomic(path/'manifest.json',manifest)
            return {'workspace_id':key,'commit':commit,'branch':'cora/'+key,'base_commit':manifest['base_commit']}

    def submit(self, kind, key='', commit='', release_id=''):
        with self.lock:
            if self.closed.is_set():raise ValueError('Servizio in arresto: controllare il servizio host.')
            if any(j['status'] in BUSY | {'recovery_required'} for j in self.list_jobs()): raise ValueError('Un job di aggiornamento è già in corso.')
            if kind=='prepare':
                path,manifest=self.workspace(key)
                if commit != manifest.get('commit') or self.scan(path/'files') != manifest.get('committed_files'):
                    raise ValueError('Salva un commit della versione corrente prima di preparare il rilascio.')
                if manifest['base_commit']!=self.current()['commit']: raise ValueError('Il workspace deriva da una versione superata; crea un nuovo workspace Git.')
                base=manifest['base_commit']
            elif kind in {'apply','rollback','publish'}:
                release=self.load(release_id)
                if release['kind']!='prepare' or release['commit']!=commit: raise ValueError('Rilascio o commit non corrispondente.')
                if kind=='publish':
                    self.remote()
                    if release['status'] not in {'ready','applied','rolled_back'}:raise ValueError('Pubblica solo rilasci verificati.')
                if kind=='apply' and (release['status']!='ready' or release['base_commit']!=self.current()['commit']):
                    raise ValueError('Rilascio non pronto o versione attiva cambiata.')
                if kind=='rollback' and (release.get('applied_job') is None or self.current()['commit']!=commit):
                    raise ValueError('Puoi ripristinare soltanto il rilascio attualmente attivo.')
                key=release['workspace_id']; base=release['base_commit']
            else: raise ValueError('Operazione non consentita.')
            identifier=str(uuid4()); self.path(identifier).mkdir()
            row={'id':identifier,'kind':kind,'workspace_id':key,'commit':commit,'base_commit':base,
                 'release_id':release_id,'status':'queued','phase':'queued','created_at':now()}
            self.save(row); self.wakeup.set(); return self.public(row)

    def build(self, row):
        folder=self.path(row['id']); source=folder/'source'; source.mkdir(exist_ok=True)
        with (folder/'source.tar').open('wb') as output: self.git_archive(row['commit'], output)
        with tarfile.open(folder/'source.tar') as archive: archive.extractall(source,filter='data')
        self.scan(source)
        changed=self.git('diff','--name-only',row['base_commit'],row['commit']).splitlines()
        if 'compose.yml' in changed:raise ValueError('compose.yml modifica la configurazione host: serve una revisione/installazione separata del servizio updater.')
        self.phase(row,'building')
        tags={name:'cora-candidate-'+row['id']+'-'+name for name in ('api','web')}
        for name in tags:
            target=self.config['api_target'] if name=='api' else 'web'
            self.cmd(['docker','build','--target',target,'--build-arg','CORA_UID='+str(self.config['uid']),
                      '--build-arg','CORA_GID='+str(self.config['gid']),'-t',tags[name],str(source)],timeout=1800)
        images={name:self.cmd(['docker','image','inspect','--format={{.Id}}',tag],timeout=30) for name,tag in tags.items()}
        self.phase(row,'testing')
        output=self.cmd(['docker','run','--rm','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
                  '--pids-limit=256','--memory=2g','--cpus=2','--tmpfs=/tmp:rw,nosuid,size=256m',
                  '--entrypoint=python',images['api'],'-m','unittest','discover','-s','tests','-v'],timeout=300)
        summary=re.search(r'Ran (\d+) tests?',output);skipped=re.search(r'skipped=(\d+)',output)
        if not summary or int(summary[1]) <= (int(skipped[1]) if skipped else 0):raise ValueError('Nessun test Python effettivamente eseguito.')
        row['images']=images; row['checks']={'images_built':True,'frontend_build':True,'python_suite':True}
        row['status']='ready'; self.phase(row,'ready')

    def git_archive(self, commit, output):
        self.cmd(['git','--git-dir='+str(self.repo),'archive','--format=tar',commit],stdout=output,timeout=60)

    def images(self):
        result={}
        for name in ('api','web'):
            container=self.compose('ps','-q',name,timeout=30)
            if not container or '\n' in container: raise ValueError('Serve una sola istanza attiva per '+name)
            result[name]=self.cmd(['docker','inspect','--format={{.Image}}',container],timeout=30)
        return result

    def backup(self, row):
        folder=self.path(row['id'])/'backup'; folder.mkdir(exist_ok=True)
        self.phase(row,'stopping')
        self.compose('stop','-t','330','web','api',timeout=400)
        self.phase(row,'backing_up')
        with (folder/'database.dump').open('wb') as output:
            self.compose('exec','-T','postgres','sh','-c','exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc',stdout=output)
        with tarfile.open(folder/'state.tar.gz','w:gz') as archive: archive.add(self.state,arcname='state')
        manifest={p.name:file_digest(p) for p in (folder/'database.dump',folder/'state.tar.gz')}
        atomic(folder/'manifest.json',manifest)
        row['backup_valid']=True; self.phase(row,'backup_complete')

    def validate_backup(self, job_id):
        folder=self.path(job_id)/'backup'; manifest=json.loads((folder/'manifest.json').read_text())
        if set(manifest)!={'database.dump','state.tar.gz'}: raise ValueError('Backup incompleto.')
        for name,digest in manifest.items():
            if file_digest(folder/name)!=digest: raise ValueError('Backup danneggiato.')
        return folder

    def restore(self, row, backup_id, images, commit):
        folder=self.validate_backup(backup_id)
        # Validate extraction before removing live files. Refuse external symlinks.
        temporary=self.path(row['id'])/'restore-state'
        if temporary.exists(): shutil.rmtree(temporary)
        temporary.mkdir()
        with tarfile.open(folder/'state.tar.gz') as archive: archive.extractall(temporary,filter='data')
        row['restore_may_have_started']=True
        self.phase(row,'restoring')
        self.compose('stop','-t','330','web','api',timeout=400)
        # Cora owns this database. Restoring the complete database also restores migration metadata.
        self.compose('exec','-T','postgres','psql','-U','cora','-d','postgres','-v','ON_ERROR_STOP=1','-c','DROP DATABASE IF EXISTS cora WITH (FORCE);')
        self.compose('exec','-T','postgres','psql','-U','cora','-d','postgres','-v','ON_ERROR_STOP=1','-c','CREATE DATABASE cora OWNER cora;')
        with (folder/'database.dump').open('rb') as source:
            self.compose('exec','-T','postgres','pg_restore','-U','cora','-d','cora','--exit-on-error','--no-owner','--no-privileges',stdin=source)
        for path in self.state.iterdir():
            if path.is_dir() and not path.is_symlink(): shutil.rmtree(path)
            else: path.unlink()
        for path in (temporary/'state').iterdir(): shutil.move(str(path),str(self.state/path.name))
        if os.getuid()==0:
            for path in [self.state,*self.state.rglob('*')]:os.chown(path,self.config['uid'],self.config['gid'],follow_symlinks=False)
        self.compose('up','-d','--no-build','--pull','never','--wait','--wait-timeout','180','api','web',images=images,timeout=550)
        atomic(self.root/'current.json',{'commit':commit,'images':images,'updated_at':now()})
        row['rollback']='restored'; self.save(row)

    def migration_trial(self, row, image):
        """Run schema upgrades on a disposable copy, never on the live database."""
        network='cora-trial-'+row['id']; container=network+'-db'; password=secrets.token_hex(24)
        pg=self.compose('ps','-q','postgres',timeout=30)
        pg_image=self.cmd(['docker','inspect','--format={{.Image}}',pg],timeout=30)
        created_network=False;created_container=False
        self.phase(row,'migration_trial')
        try:
            self.cmd(['docker','network','create','--internal',network],timeout=30);created_network=True
            self.cmd(['docker','run','--detach','--pull=never','--name',container,'--network',network,
                      '--memory=2g','--pids-limit=256','--tmpfs=/var/lib/postgresql/data:rw,nosuid,size=2g',
                      '-e','POSTGRES_USER=cora','-e','POSTGRES_DB=cora','-e','POSTGRES_PASSWORD='+password,pg_image],timeout=30)
            created_container=True
            import time
            deadline=time.monotonic()+60
            while True:
                try:self.cmd(['docker','exec',container,'pg_isready','-U','cora','-d','cora'],timeout=5);break
                except RuntimeError:
                    if time.monotonic()>deadline:raise TimeoutError('Database di prova non pronto.')
                    time.sleep(.2)
            with (self.path(row['id'])/'backup'/'database.dump').open('rb') as source:
                self.cmd(['docker','exec','-i',container,'pg_restore','-U','cora','-d','cora','--exit-on-error','--no-owner','--no-privileges'],stdin=source)
            self.cmd(['docker','run','--rm','--network',network,'--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
                      '--pids-limit=128','--memory=1g','--tmpfs=/tmp:rw,nosuid,size=128m',
                      '-e','CORA_DATABASE_URL=postgresql://cora:'+password+'@'+container+':5432/cora',
                      '--entrypoint=python',image,'-c',
                      "from core.database import db_connection; c=db_connection(); conn=c.__enter__();conn.execute('SELECT 1');c.__exit__(None,None,None)"],timeout=300)
            row['checks']={'migration_copy':True};self.save(row)
        finally:
            if created_container:self.cmd(['docker','rm','--force',container],timeout=30)
            if created_network:self.cmd(['docker','network','rm',network],timeout=30)

    def apply(self, row):
        release=self.load(row['release_id'])
        if self.current()['commit']!=row['base_commit']: raise ValueError('La versione attiva è cambiata.')
        row['previous_commit']=self.current()['commit']; row['previous_images']=self.images(); self.save(row)
        self.backup(row)
        self.migration_trial(row,release['images']['api'])
        row['candidate_may_have_started']=True
        self.phase(row,'candidate_starting')
        self.compose('up','-d','--no-build','--pull','never','--wait','--wait-timeout','180','api','web',images=release['images'],timeout=550)
        # Confirm HTTP and a real DB connection in addition to container healthchecks.
        self.compose('exec','-T','api','python','-c',
                     "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/auth/status',timeout=5)\nfrom core.database import db_connection\nwith db_connection() as conn: conn.execute('SELECT 1')",timeout=30)
        atomic(self.root/'current.json',{'commit':row['commit'],'images':release['images'],'updated_at':now()})
        release['applied_job']=row['id']; release['status']='applied'; self.save(release)
        row['status']='completed'; self.phase(row,'completed')

    def rollback(self, row):
        release=self.load(row['release_id']); original=self.load(release['applied_job'])
        # Preserve newer data separately before a requested restore to the old snapshot.
        row['previous_commit']=self.current()['commit']; row['previous_images']=self.images(); self.save(row)
        self.backup(row)
        self.restore(row,original['id'],original['previous_images'],original['previous_commit'])
        release['status']='rolled_back';self.save(release)
        row['status']='completed'; self.phase(row,'completed')

    def cleanup_trial(self, row):
        self.cmd(['docker','info','--format={{.ID}}'],timeout=30)
        name='cora-trial-'+row['id']
        for object_type,identifier in [('container',name+'-db'),('network',name)]:
            try:self.cmd(['docker',object_type,'inspect',identifier],timeout=30)
            except RuntimeError:continue
            self.cmd(['docker',object_type,'rm',*(['--force'] if object_type=='container' else []),identifier],timeout=30)

    def recover(self, row):
        if row['phase']=='migration_trial':self.cleanup_trial(row)
        if row['kind'] in {'apply','rollback'} and row.get('previous_images'):
            if row.get('backup_valid') and (row.get('candidate_may_have_started') or row.get('restore_may_have_started') or row['phase'] in {'candidate_starting','restoring'}):
                self.restore(row,row['id'],row['previous_images'],row['previous_commit'])
            else:
                self.compose('up','-d','--no-build','--pull','never','--wait','--wait-timeout','180','api','web',images=row['previous_images'],timeout=550)
                row['rollback']='previous_services_restarted'
        if row['kind']=='apply' and row.get('release_id'):
            release=self.load(row['release_id']);release['status']='ready';release.pop('applied_job',None);self.save(release)
        row['status']='failed'; self.save(row)

    def execute(self, row):
        row['status']='running'; self.save(row)
        try:
            {'prepare':self.build,'apply':self.apply,'rollback':self.rollback,'publish':self.publish}[row['kind']](row)
        except BaseException as error:
            row['error']=type(error).__name__+': '+str(error)[:300]
            try: self.recover(row)
            except BaseException:
                row['status']='recovery_required'; row['error']='Ripristino non completato: controllare il servizio updater dal server.'; self.save(row)

    def start(self):
        def loop():
            for entry in self.list_jobs():
                row=self.load(entry['id'])
                if row['status']=='running':
                    row['error']='Servizio riavviato durante il lavoro.'
                    try: self.recover(row)
                    except BaseException: row['status']='recovery_required'; self.save(row)
            while not self.closed.is_set():
                with self.lock:
                    queued=next((self.load(r['id']) for r in reversed(self.list_jobs()) if r['status']=='queued'),None)
                if queued: self.execute(queued)
                else: self.wakeup.wait(1); self.wakeup.clear()
        def guarded_loop():
            try:loop()
            finally:self.closed.set()
        self.worker=threading.Thread(target=guarded_loop,name='cora-updater',daemon=True); self.worker.start()
