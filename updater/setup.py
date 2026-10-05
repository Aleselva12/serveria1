"""One-time host provisioning. Run from the trusted version installed manually."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
from updater.engine import atomic


def initialize(root, project_root, active_commit, listen='', port=9021, github_repository='', github_branch='main'):
    import re
    if github_repository and not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',github_repository):raise ValueError('Usa owner/repository per GitHub.')
    subprocess.run(['git','check-ref-format','refs/heads/'+github_branch],check=True)
    root=Path(root).resolve();project_root=Path(project_root).resolve()
    if root.exists(): raise ValueError('Directory updater già presente; non viene sovrascritta.')
    deploy=project_root/'deploy.env'
    settings={}
    for line in deploy.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key,value=line.split('=',1);settings[key]=value.strip().strip('"\'')
    state=Path(settings.get('CORA_STATE_ROOT','./state'))
    if not state.is_absolute():state=project_root/state
    state=state.resolve()
    if root==state or root.is_relative_to(state) or root==project_root or root.is_relative_to(project_root):
        raise ValueError('Updater deve stare fuori dal codice e dallo stato Cora.')
    if not state.is_dir() or state.is_symlink(): raise ValueError('Stato Cora non disponibile.')
    if settings.get('CORA_API_BUILD_TARGET','api') not in {'api','api-audio-cpu'}:raise ValueError('Target API non supportato.')
    revision=subprocess.check_output(['git','rev-parse',active_commit+'^{commit}'],cwd=project_root,text=True).strip()
    if not listen:
        listen=subprocess.check_output(['docker','network','inspect','bridge','--format={{(index .IPAM.Config 0).Gateway}}'],text=True).strip()
    if os.getuid()!=0 and int(settings.get('CORA_UID',os.getuid()))!=os.getuid():
        raise ValueError('Esegui il servizio con lo stesso UID del container Cora.')
    root.mkdir(mode=0o700)
    original=deploy.read_text();original_mode=deploy.stat().st_mode & 0o777
    try:
        token=secrets.token_hex(32);(root/'bridge.token').write_text(token+'\n');(root/'bridge.token').chmod(0o600)
        # Cora may request fixed operations; no socket or host Git credential enters its container.
        bridge='http://host.docker.internal:'+str(port)
        updated=original+'\nCORA_UPDATER_URL='+bridge+'\nCORA_UPDATER_TOKEN='+token+'\n'
        deploy.write_text(updated);deploy.chmod(0o600)
        resolved=subprocess.check_output(['docker','compose','--env-file',str(deploy),'-f',str(project_root/'compose.yml'),'config','--format','json'],cwd=project_root,text=True)
        config=json.loads(resolved)
        # Resolve before installation; runtime changes to compose.yml do not change host authority.
        atomic(root/'compose.json',config);(root/'compose.json').chmod(0o600)
        subprocess.run(['git','clone','--bare','--no-hardlinks',str(project_root),str(root/'repo.git')],check=True,stdout=subprocess.DEVNULL)
        atomic(root/'current.json',{'commit':revision,'updated_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()})
        atomic(root/'config.json',{'state_root':str(state),'project':config.get('name','cora'),'api_target':settings.get('CORA_API_BUILD_TARGET','api'),
                                 'uid':int(settings.get('CORA_UID',os.getuid())),'gid':int(settings.get('CORA_GID',os.getgid())), 'listen':listen,'port':port,'github_repository':github_repository,'github_branch':github_branch})
        shutil.copytree(Path(__file__).parent,root/'installed'/'updater',ignore=shutil.ignore_patterns('__pycache__'))
        (root/'jobs').mkdir()
    except BaseException:
        deploy.write_text(original);deploy.chmod(original_mode)
        shutil.rmtree(root)
        raise
    print('Updater preparato. Avvia il servizio separato e ricrea API/web per caricare la configurazione bridge.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--project-root',default='.');p.add_argument('--active-commit',required=True);p.add_argument('--listen',default='');p.add_argument('--port',type=int,default=9021);p.add_argument('--github-repository',default='');p.add_argument('--github-branch',default='main');args=p.parse_args()
    initialize(args.root,args.project_root,args.active_commit,args.listen,args.port,args.github_repository,args.github_branch)

if __name__=='__main__':main()
