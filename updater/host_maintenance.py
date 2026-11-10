"""Standalone helper copied outside installed/. Runs as ale, never as root."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import Request, build_opener, ProxyHandler


def write(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def control(action):
    subprocess.run(['/usr/bin/sudo','-n','/usr/bin/systemctl',action,'cora-updater.service'], check=True, timeout=40)


def healthy(root, expected=None):
    config = json.loads((root/'config.json').read_text())
    host = config['listen']
    if host == '0.0.0.0': host = '127.0.0.1'
    request = Request('http://'+host+':'+str(config['port'])+'/host/maintenance',
                      headers={'Authorization':'Bearer '+(root/'bridge.token').read_text().strip()})
    opener = build_opener(ProxyHandler({}))
    for _ in range(30):
        try:
            with opener.open(request, timeout=2) as response:
                value = json.load(response)
            if value.get('available') and (expected is None or value.get('digest') == expected):
                return True
        except Exception: pass
        time.sleep(1)
    return False


def execute(root, service=control, health=healthy):
    root = Path(root)
    request = root/'maintenance.request'
    journal = root/'maintenance.journal.json'
    if not request.exists() and not journal.exists(): return
    installed, previous, candidate = (root/name for name in ('installed','maintenance.previous','maintenance.next'))
    if journal.exists():
        # An interrupted operation never resumes an unverified candidate.
        state = json.loads(journal.read_text())
    else:
        state = {**json.loads(request.read_text()), 'phase':'prepared'}
        if previous.exists():
            import shutil
            shutil.rmtree(previous)
        write(journal, state)
    try:
        service('stop')
        with (root/'service.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if state['phase'] != 'prepared':
                raise RuntimeError('Interrupted update')
            # Persist intent BEFORE each rename, so a killed helper can restore.
            state['phase'] = 'switching'; write(journal,state)
            installed.rename(previous)
            candidate.rename(installed)
            state['phase'] = 'verifying'; write(journal,state)
        service('start')
        if not health(root, state['digest']): raise RuntimeError('Candidate unhealthy')
        result = {'status':'completed','commit':state['commit'],'digest':state['digest'],'rollbackAvailable':True}
    except Exception:
        try:
            service('stop')
            if previous.exists():
                if installed.exists():
                    import shutil
                    failed = root/'maintenance.failed'
                    if failed.exists(): shutil.rmtree(failed)
                    installed.rename(failed)
                previous.rename(installed)
            service('start')
            if not health(root): raise RuntimeError('Rollback unhealthy')
            result = {'status':'rolled_back','commit':state['commit']}
        except Exception:
            write(root/'maintenance.result.json', {'status':'recovery_required','commit':state['commit']})
            # Keep request and journal; block new writes until operator recovery.
            raise
    write(root/'maintenance.result.json', result)
    journal.unlink(missing_ok=True)
    request.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True)
    root=Path(parser.parse_args().root).resolve()
    with (root/'maintenance.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        execute(root)

if __name__ == '__main__': main()
