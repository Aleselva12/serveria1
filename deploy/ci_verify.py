"""Disposable CI deployment only: includes deleting test volumes and state."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
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
    manage.init()
    target=os.getenv('CORA_CI_API_TARGET','api')
    if target not in {'api','api-audio-cpu'}:raise ValueError('Invalid CI build target')
    def configure():
        content=manage.ENV.read_text().replace('CORA_API_BUILD_TARGET=api\n','CORA_API_BUILD_TARGET='+target+'\n')
        manage.ENV.write_text(content)
    configure();manage.compose('config','--quiet');manage.compose('up','-d','--build','--wait','--wait-timeout','180')
    try:
        if target=='api-audio-cpu':
            manage.compose('run','--rm','--no-deps','-T','-e','HF_HUB_OFFLINE=0','api','python','-m','audio_agent.model_setup','--model','tiny')
            manage.compose('exec','-T','api','python','-m','audio_agent.model_setup','--check')
            inference="""import wave
from pathlib import Path
from audio_agent.audio_tools import _load_whisper_model
path=Path('/state/audio/ci-silence.wav')
with wave.open(str(path),'wb') as stream:
    stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(16000);stream.writeframes(b'\\x00\\x00'*16000)
segments,info=_load_whisper_model().transcribe(str(path),language='it',vad_filter=False)
list(segments)
print('CPU WHISPER OFFLINE INFERENCE: OK')
"""
            manage.compose('exec','-T','api','python','-',input=inference,text=True)
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
        shutil.rmtree(ROOT/'state');manage.ENV.unlink();manage.init();configure()
        manage.restore(backup);manage.compose('up','-d','--wait','--wait-timeout','180')
        with request('/backend/auth/status',cookie=cookie) as response:assert not json.load(response)['authenticated']
        with request('/backend/auth/login',{'username':'ci-owner','password':'ci-private-password-123'}) as response:
            cookie=response.headers['Set-Cookie'].split(';')[0]
        restored=manage.compose('exec','-T','api','cat','/state/files/proof.txt',capture_output=True,text=True).stdout.strip()
        assert restored==run_id
        with request('/backend/api/v1/runtime/runs/'+run_id, cookie=cookie) as response:assert json.load(response)['status']=='completed'
        from updater.ci_verify import verify as verify_updater
        verify_updater(ROOT)
        print('DEPLOYMENT BUILD, LOGIN, SSE, BACKUP AND RESTORE: OK')
    finally:
        manage.compose('logs','--no-color','--tail','80')
        manage.compose('down','--volumes')


if __name__=='__main__':main()
