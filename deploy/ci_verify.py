"""Disposable CI deployment only: includes deleting test volumes and state."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('manage',ROOT/'deploy/manage.py')
manage=importlib.util.module_from_spec(spec);spec.loader.exec_module(manage)


def request(path,data=None,cookie=None):
    headers={'X-Cora-Client':'ui'}
    if cookie:headers['Cookie']=cookie
    body=json.dumps(data).encode() if data is not None else None
    if body is not None:headers['Content-Type']='application/json'
    return urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8080'+path,body,headers),timeout=15)


def main():
    # Never run the destructive fixture against an ordinary user's installation.
    import os
    if os.getenv('GITHUB_ACTIONS')!='true' or os.getenv('CORA_DISPOSABLE_DEPLOY_TEST')!='yes':
        raise RuntimeError('This fixture requires disposable GitHub Actions infrastructure')
    manage.init();manage.compose('config','--quiet');manage.compose('up','-d','--build','--wait','--wait-timeout','180')
    try:
        source="""from pathlib import Path
from core.auth import provision
from core.run_lifecycle import create_run,transition_run
provision('ci-owner','ci-private-password-123')
run=create_run(thread_id='ci-backup-proof')
transition_run(str(run['id']),'running')
transition_run(str(run['id']),'completed',result={'response':'fixture'})
Path('/state/files/proof.txt').write_text(str(run['id']))
"""
        manage.compose('exec','-T','api','python','-',input=source,text=True)
        with request('/backend/auth/login',{'username':'ci-owner','password':'ci-private-password-123'}) as response:
            cookie=response.headers['Set-Cookie'].split(';')[0]
        with request('/backend/api/v1/runtime',cookie=cookie) as response:assert json.load(response)['version']==3
        run_id=manage.compose('exec','-T','api','cat','/state/files/proof.txt',capture_output=True,text=True).stdout.strip()
        with request('/backend/api/v1/runtime/runs/'+run_id+'/events',cookie=cookie) as response:
            stream=response.read().decode();assert 'event: result' in stream and 'fixture' in stream
        backup=ROOT/'backups/ci-proof';manage.backup(backup);manage.check_backup(backup)
        manage.compose('down','--volumes')
        shutil.rmtree(ROOT/'state');manage.ENV.unlink();manage.init()
        manage.restore(backup);manage.compose('up','-d','--wait','--wait-timeout','180')
        with request('/backend/auth/status',cookie=cookie) as response:assert not json.load(response)['authenticated']
        with request('/backend/auth/login',{'username':'ci-owner','password':'ci-private-password-123'}) as response:
            cookie=response.headers['Set-Cookie'].split(';')[0]
        restored=manage.compose('exec','-T','api','cat','/state/files/proof.txt',capture_output=True,text=True).stdout.strip()
        assert restored==run_id
        with request('/backend/api/v1/runtime/runs/'+run_id, cookie=cookie) as response:assert json.load(response)['status']=='completed'
        print('DEPLOYMENT BUILD, LOGIN, SSE, BACKUP AND RESTORE: OK')
    finally:
        manage.compose('logs','--no-color','--tail','80')
        manage.compose('down','--volumes')


if __name__=='__main__':main()
