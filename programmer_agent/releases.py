"""Authenticated fixed-operation bridge. No host shell or token reaches the model/browser."""
import os
from urllib.parse import urlparse
import httpx
from programmer_agent import workspace as ws


def request(method, path, data=None):
    base=os.getenv('CORA_UPDATER_URL','').rstrip('/')
    token=os.getenv('CORA_UPDATER_TOKEN','')
    parsed=urlparse(base)
    if not base or not token: raise ValueError('Servizio aggiornamenti non configurato sul server. Segui updater/README.md.')
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('URL updater non valido.')
    try:
        with httpx.Client(timeout=60,trust_env=False,follow_redirects=False) as client:
            response=client.request(method,base+path,json=data,headers={'Authorization':'Bearer '+token})
        value=response.json()
        if response.status_code>=400:raise ValueError(value.get('detail','Operazione updater non riuscita.'))
        return value
    except (httpx.HTTPError,ValueError) as error:
        if isinstance(error,ValueError):raise
        raise ValueError('Updater non raggiungibile. La richiesta non viene ripetuta automaticamente: controlla lo stato dei job.') from error


def status():
    if not os.getenv('CORA_UPDATER_URL') or not os.getenv('CORA_UPDATER_TOKEN'):
        return {'available':False,'reason':'Servizio aggiornamenti non configurato','jobs':[]}
    return request('GET','/status')


def create(title): return request('POST','/workspaces',{'title':title})


def commit(identifier,message):
    ws.directory(identifier)
    with ws.LOCK:
        return request('POST','/workspaces/'+identifier+'/commit',{'message':message})


def prepare(identifier,expected_commit):
    manifest=ws.manifest(identifier)
    if manifest.get('mode')!='git' or manifest.get('commit')!=expected_commit:
        raise ValueError('Crea un workspace Git e salva il commit corrente.')
    with ws.LOCK:
        return request('POST','/jobs',{'kind':'prepare','workspace_id':identifier,'commit':expected_commit})


def job(identifier,job_id):
    from uuid import UUID
    value=request('GET','/jobs/'+str(UUID(job_id)))
    if value['workspace_id']!=identifier:raise ValueError('Job appartenente a un altro workspace.')
    return value


def apply(identifier,release_id,expected_commit,kind='apply'):
    value=job(identifier,release_id)
    if value['commit']!=expected_commit:raise ValueError('Commit cambiato: ricontrolla il rilascio.')
    return request('POST','/jobs',{'kind':kind,'release_id':release_id,'commit':expected_commit})
