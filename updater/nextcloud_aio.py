"""Fixed operations for an existing Nextcloud AIO installation. No image downgrade."""
import json
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone
from updater.engine import atomic

MASTER='nextcloud-aio-mastercontainer'
BACKUP='nextcloud-aio-borgbackup'
NEXTCLOUD='nextcloud-aio-nextcloud'
RECOVERY='Controllare AIO e il backup prima di altre operazioni. Ripristino dal pannello AIO; nessun downgrade automatico.'


def command(args, timeout=30, capture=True):
    result=subprocess.run(['docker',*args],stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL,text=True,timeout=timeout)
    if result.returncode: raise RuntimeError('Operazione AIO non riuscita')
    return result.stdout or ''


class NextcloudAIO:
    def __init__(self, root, run=command, sleep=time.sleep):
        self.root=Path(root);self.run=run;self.sleep=sleep
        self.file=self.root/'nextcloud-aio.json'
        self.job=json.loads(self.file.read_text()) if self.file.exists() else {'status':'idle'}
        if self.job['status']=='running':
            self.save(status='recovery_required',message=RECOVERY)

    def save(self, **fields):
        self.job={**self.job,**fields,'updatedAt':datetime.now(timezone.utc).isoformat()}
        self.root.mkdir(parents=True,exist_ok=True)
        atomic(self.file,self.job)
        return dict(self.job)

    def inspect(self, name):
        # Select only required fields; never retrieve environment/passwords.
        value=self.run(['inspect','--format','{"id":{{json .Id}},"state":{{json .State}}}',name])
        return json.loads(value)

    def version(self):
        return json.loads(self.run(['exec','--user','www-data',NEXTCLOUD,'php','occ','status','--output=json']))

    def ready(self):
        for name in (MASTER,NEXTCLOUD,'nextcloud-aio-apache','nextcloud-aio-database'):
            state=self.inspect(name)['state']
            if not state.get('Running') or state.get('Health',{}).get('Status')!='healthy':return False
        version=self.version()
        return version.get('installed') is True and version.get('maintenance') is False and version.get('needsDbUpgrade') is False

    def status(self):
        result={'id':'nextcloud-aio','name':'Nextcloud AIO','repository':'Gestito dal mastercontainer AIO',
                'installed':False,'configured':False,'running':False,'job':dict(self.job),
                'recoveryUrl':'https://serverale:8080','commit':None}
        try:
            self.inspect(MASTER);result['installed']=True
            self.inspect(BACKUP);result['configured']=True
            result['running']=self.ready()
            result['commit']=self.version().get('versionstring')
        except (RuntimeError,OSError,ValueError,subprocess.TimeoutExpired):pass
        return result

    def preflight(self):
        if not self.ready():raise ValueError('Nextcloud AIO non pronto: verificare il pannello AIO.')
        if self.inspect(BACKUP)['state'].get('Running'):raise ValueError('Backup o ripristino AIO già in corso.')
        self.run(['exec',MASTER,'test','!','-f','/mnt/docker-aio-config/data/daily_backup_running'])

    def script(self, update):
        # Explicitly override every mode: inherited container settings cannot skip backup.
        flags={'DAILY_BACKUP':'0' if update else '1','AUTOMATIC_UPDATES':'1' if update else '0',
               'CHECK_BACKUP':'0','START_CONTAINERS':'1','STOP_CONTAINERS':'0'}
        args=['exec']
        for key,value in flags.items():args+=['--env',key+'='+value]
        self.run([*args,MASTER,'/daily-backup.sh'],timeout=7200,capture=False)

    def execute(self):
        try:
            self.save(status='running',phase='preflight',message='Verifica prerequisiti AIO')
            self.preflight()
            before=self.version();old_backup=self.inspect(BACKUP)['state'].get('FinishedAt')
            self.save(phase='backup',beforeVersion=before.get('versionstring'),message='Backup AIO prima dell’aggiornamento')
            self.script(False)
            state=self.inspect(BACKUP)['state']
            if state.get('Running') or state.get('ExitCode')!=0 or not state.get('FinishedAt') or state['FinishedAt']==old_backup:
                raise RuntimeError('Backup non verificato')
            if not self.ready():raise RuntimeError('AIO non pronto dopo il backup')
            self.save(phase='update',backupFinishedAt=state['FinishedAt'],message='Aggiornamento tramite AIO')
            old_master=self.inspect(MASTER)['id']
            interrupted=False
            try:self.script(True)
            except (RuntimeError,subprocess.TimeoutExpired):interrupted=True
            if interrupted or self.inspect(MASTER)["id"] != old_master:
                # AIO documents one continuation after replacing its mastercontainer.
                changed=False
                for _ in range(60):
                    try:
                        master=self.inspect(MASTER)
                        changed=master['id']!=old_master and master['state'].get('Health',{}).get('Status')=='healthy'
                    except (RuntimeError,ValueError):pass
                    if changed:break
                    self.sleep(2)
                if not changed:raise RuntimeError("Mastercontainer non sostituito o non pronto")
                self.save(phase='resume_after_master_update',message='Nuovo mastercontainer pronto; completamento aggiornamento')
                self.script(True)
            self.save(phase='verify',message='Verifica stato e migrazioni Nextcloud')
            for _ in range(60):
                try:
                    if self.ready():break
                except (RuntimeError,ValueError):pass
                self.sleep(2)
            else:raise RuntimeError('Health finale non riuscita')
            self.save(status='completed',phase='ready',afterVersion=self.version().get('versionstring'),message='Backup e aggiornamento AIO completati')
        except Exception:
            self.save(status='recovery_required',message=RECOVERY)
