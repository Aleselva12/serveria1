"""Local installation checks: no model generation, credential dump or audio upload."""
import importlib.util
import json
import os
from pathlib import Path
from urllib.request import build_opener,ProxyHandler


def urlopen(url,timeout):
    return build_opener(ProxyHandler({})).open(url,timeout=timeout)


def model_available(name,names):
    return name in names or (':' not in name and name+':latest' in names)


def inspect():
    checks={}
    try:
        from core.database import db_connection
        with db_connection(ensure_schema=False) as conn:
            row=conn.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector') AS vector").fetchone()
            migrations=conn.execute('SELECT COUNT(*) AS n FROM cora_schema_migrations').fetchone()['n']
        checks['database']={'ok':bool(row['vector'] and migrations),'migrations':migrations}
    except Exception as error:checks['database']={'ok':False,'error_type':type(error).__name__}
    try:
        from core.models import get_model_name
        endpoint=os.getenv('OLLAMA_BASE_URL','http://localhost:11435').rstrip('/')
        with urlopen(endpoint+'/api/tags',timeout=5) as response:data=json.load(response)
        names={model['name'] for model in data.get('models',[])}
        requested={get_model_name(role) for role in ('supervisor','structure','research','audio','email')}
        embedding=os.getenv('CORA_EMBEDDING_MODEL','').strip()
        if embedding:requested.add(embedding)
        missing=sorted(name for name in requested if not model_available(name,names))
        checks['ollama']={'ok':not missing,'missing_models':missing}
    except Exception as error:checks['ollama']={'ok':False,'error_type':type(error).__name__}
    try:
        from core.server_files import roots
        directories=[(r['id'],Path(r['path']),r['writable']) for r in roots()]
        for name in ('CORA_KNOWLEDGE_ROOT','CORA_AUDIO_ROOT','CORA_TRANSCRIPT_ROOT','CORA_STRUCTURE_WORKSPACE','CORA_AUTOMATION_ROOT','CORA_QUOTE_ROOT'):
            if os.getenv(name):directories.append((name,Path(os.environ[name]),True))
        paths=[{'id':name,'ok':path.is_dir() and os.access(path,os.R_OK|(os.W_OK if writable else 0))} for name,path,writable in directories]
        checks['storage']={'ok':all(p['ok'] for p in paths),'resources':paths}
    except Exception as error:checks['storage']={'ok':False,'error_type':type(error).__name__}
    audio=os.getenv('CORA_API_BUILD_TARGET')=='api-audio-cpu'
    if audio:
        try:
            from audio_agent.model_setup import verify
            manifest=verify(Path(os.environ['CORA_WHISPER_MODEL']))
            checks['audio']={'ok':importlib.util.find_spec('faster_whisper') is not None,
                             'model':manifest['model'],'revision':manifest['revision'],'device':'cpu'}
        except Exception as error:checks['audio']={'ok':False,'error_type':type(error).__name__}
    return {'ok':all(check['ok'] for check in checks.values()),'checks':checks,'audio_enabled':audio}


if __name__=='__main__':
    result=inspect();print(json.dumps(result,indent=2));raise SystemExit(0 if result['ok'] else 1)
