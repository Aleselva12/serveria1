"""Server evidence collector. Stdlib host; explicit, separate active probes.

Never prints container environments, credentials, prompts, responses or check logs.
Does not restart services, update releases, change models or restore data.
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID


class ProbeError(RuntimeError):
    pass


def command(args, *, cwd=None, source=None, timeout=30):
    try:
        result = subprocess.run(args, cwd=cwd, input=source, text=True,
                                capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProbeError(type(error).__name__) from None
    if result.returncode:
        # stderr can contain interpolated secrets or model content.
        raise ProbeError(f"command_exit_{result.returncode}")
    return result.stdout.strip()


def container_summary(data):
    """Allowlist the useful inspect fields; never serialize Config.Env."""
    state = data.get("State", {})
    return {"id": data["Id"], "image_id": data["Image"],
            "image": data["Config"]["Image"], "user": data["Config"].get("User", ""),
            "running": state.get("Running", False),
            "health": state.get("Health", {}).get("Status", "not_configured"),
            "mounts": [{key: mount.get(key) for key in ("Type", "Source", "Destination", "RW")}
                       for mount in data.get("Mounts", [])]}


INVENTORY = '''
import json, os
from pathlib import Path
from unittest.mock import patch
from deploy.doctor import inspect
from core.models import get_model_name, ROLE_MODEL_ENV
from programmer_agent import workspace, releases
def existing_directory(path, *args, **kwargs):
    # Legacy roots() initializes default directories. A diagnostic must instead
    # fail storage checks if the directory is absent, without creating it.
    if not path.is_dir(): raise FileNotFoundError('Directory absent')
with patch.object(Path, 'mkdir', existing_directory):
    doctor = inspect()
r = {"doctor": doctor, "uid": os.getuid(), "gid": os.getgid(),
     "models": {role: get_model_name(role) for role in ROLE_MODEL_ENV},
     "workspace_root": str(workspace.root()),
     "workspace_writable": os.access(workspace.root() if workspace.root().exists() else workspace.root().parent, os.W_OK),
     "docker_socket_present": Path('/var/run/docker.sock').exists()}
try:
    status = releases.status()
    r['bridge'] = {'ok': status.get('available') is True, 'commit': status.get('active_commit')}
except Exception as e:
    r['bridge'] = {'ok': False, 'error_type': type(e).__name__}
print(json.dumps(r))
'''


ISOLATION_TEST = '''import os, pathlib, unittest
class Isolation(unittest.TestCase):
    def test_isolation(self):
        self.assertEqual(os.getuid(), 65534)
        self.assertFalse(pathlib.Path('/var/run/docker.sock').exists())
        self.assertTrue(os.statvfs('/').f_flag & os.ST_RDONLY)
        self.assertTrue(os.statvfs('/work').f_flag & os.ST_RDONLY)
        self.assertFalse(any(k.startswith('CORA_') or k in ('OLLAMA_BASE_URL','DATABASE_URL','SSH_AUTH_SOCK') for k in os.environ))
        status = pathlib.Path('/proc/self/status').read_text()
        fields = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
        self.assertEqual(int(fields['CapEff'].strip(), 16), 0)
        self.assertEqual(fields['NoNewPrivs'].strip(), '1')
        interfaces = pathlib.Path('/proc/net/dev').read_text().splitlines()[2:]
        self.assertTrue(all(line.split(':',1)[0].strip() == 'lo' for line in interfaces))
        pathlib.Path('/tmp/priority-probe').write_text('writable temporary area')
'''


def programmer_source():
    return '''
import json, tempfile, time
from pathlib import Path
from programmer_agent import workspace as ws, checks
if not __import__('os').getenv('CORA_UPDATER_URL'):
    raise RuntimeError('Host bridge required for this probe')
rows = []
def run(identifier, profile, expected=True):
    started = time.monotonic()
    try:
        result = checks.run_check(identifier, profile)
        rows.append({'workspace_id': identifier, 'profile': profile,
                     'expected_pass': expected, 'passed': result.get('passed'),
                     'ok': result.get('passed') is expected,
                     'duration_ms': round((time.monotonic()-started)*1000)})
    except Exception as e:
        rows.append({'workspace_id': identifier, 'profile': profile, 'ok': False,
                     'error_type': type(e).__name__})
with tempfile.TemporaryDirectory() as temporary:
    project = Path(temporary)
    (project/'tests').mkdir()
    (project/'tests/test_isolation.py').write_text(TEST)
    identifier = ws.create('Verifiche prioritarie: isolamento', project)['id']
run(identifier, 'python_tests')
# An intentional failing test proves failures cannot be reported as successful.
ws.write(identifier, 'tests/test_expected_failure.py',
         'import unittest\\nclass ExpectedFailure(unittest.TestCase):\\n def test_failure(self): self.fail("synthetic failure")\\n')
run(identifier, 'python_tests', False)
# Preserve both workspaces and their evidence for review in Programma.
frontend = ws.create('Verifiche prioritarie: frontend')['id']
run(frontend, 'typescript')
run(frontend, 'frontend_build')
print(json.dumps({'ok': all(row['ok'] for row in rows), 'checks': rows,
                  'intentional_failure_workspace': identifier}))
'''.replace("(TEST)", "(" + repr(ISOLATION_TEST) + ")")


OLLAMA = '''
import json, time
from urllib.request import Request
from core.models import get_model_name, get_model_keep_alive
from core.ollama_transport import urlopen, get_ollama_base_url
model = get_model_name('programmer')
samples = []
for index in range(3):
    started = time.monotonic()
    first = None
    final = None
    body = {'model': model, 'messages': [{'role':'user','content':'Rispondi soltanto con la parola PRONTO.'}],
            'stream': True, 'keep_alive': get_model_keep_alive(),
            'options': {'temperature': 0, 'num_predict': 64}}
    request = Request(get_ollama_base_url()+'/api/chat', data=json.dumps(body).encode(),
                      headers={'Content-Type':'application/json'})
    with urlopen(request, timeout=120) as response:
        for line in response:
            row = json.loads(line)
            if row.get('error'): raise RuntimeError('Provider error')
            message = row.get('message', {})
            if first is None and (message.get('content') or message.get('thinking')):
                first = round((time.monotonic()-started)*1000, 2)
            if row.get('done'): final = row
    if final is None: raise RuntimeError('Incomplete provider stream')
    sample = {'index':index+1, 'wall_ms':round((time.monotonic()-started)*1000,2),
              'first_token_ms': first, 'done_reason':final.get('done_reason')}
    for name in ('load_duration','prompt_eval_duration','eval_duration','total_duration'):
        if isinstance(final.get(name), (int,float)): sample[name+'_ms'] = round(final[name]/1e6, 2)
    for name in ('prompt_eval_count','eval_count'):
        sample[name] = final.get(name)
    samples.append(sample)
print(json.dumps({'ok': True, 'model': model, 'scope': 'direct_ollama_not_cora_pipeline',
                  'samples': samples}))
'''


def trace_source(identifier):
    identifier = str(UUID(identifier))
    return '''
import json
from core.execution_traces import read_runs
rows = read_runs(run_id=IDENTIFIER, include_events=False)
result = []
for row in rows:
    metrics = row.get('metrics', {})
    timings = {k: v for k,v in metrics.items() if k.endswith('_ms') and isinstance(v, (int,float))}
    timings['models'] = [{k: v for k,v in model.items() if k in
        ('role','duration_ms','first_token_ms','load_duration','total_duration',
         'prompt_eval_duration','eval_duration','prompt_eval_count','eval_count','error_type')}
        for model in metrics.get('models', [])]
    configuration = {k:v for k,v in metrics.get('configuration', {}).items() if k in
        ('model','profile','target','context_tokens','output_tokens','keep_alive')}
    # Inclusive node spans overlap; never add node_ms to model or elapsed time.
    model_ms = sum(m.get('duration_ms') or 0 for m in timings['models'])
    elapsed = row.get('duration_ms')
    summary = {'model_calls': len(timings['models']), 'model_ms': model_ms,
               'model_share_percent': round(100 * model_ms / elapsed, 2)
                   if elapsed and timings['models'] else None,
               'node_times_are_inclusive': True}
    for model in timings['models']:
        model['provider_ms'] = {key: round(model[key] / 1e6, 2)
            for key in ('load_duration','prompt_eval_duration','eval_duration','total_duration')
            if isinstance(model.get(key), (int, float))}
    result.append({'id':row['id'], 'status':row['status'], 'duration_ms':row.get('duration_ms'), 'configuration':configuration,
                   'timings':timings, 'summary':summary})
print(json.dumps({'ok':bool(result) and all(r['status']=='completed' for r in result),
                  'scope':'runtime_completion_not_task_correctness',
                  'provider_duration_unit':'nanoseconds', 'runs':result}))
'''.replace("IDENTIFIER", repr(identifier))


def api_probe(container, source, timeout=30):
    return json.loads(command(["docker", "exec", "-i", container, "python", "-B", "-"],
                              source=source, timeout=timeout))


def inspect_host(root, overrides, updater_root):
    files = [root / "compose.yml", *overrides]
    compose = ["docker", "compose", "--env-file", str(root / "deploy.env")]
    for path in files:
        compose += ["-f", str(path)]
    report = {"compose_files": [{"path": str(path), "exists": path.is_file()} for path in files],
              "services": {}, "checker_images": {}}
    api_id = None
    for service in ("api", "web", "postgres"):
        try:
            identifier = command([*compose, "ps", "-q", service], cwd=root)
            if not identifier or len(identifier.splitlines()) != 1:
                raise ProbeError("expected_one_running_container")
            data = json.loads(command(["docker", "inspect", identifier]))[0]
            report["services"][service] = container_summary(data)
            if service == "api": api_id = identifier
        except (ProbeError, ValueError, KeyError) as error:
            report["services"][service] = {"running": False, "error_type": str(error) if isinstance(error, ProbeError) else type(error).__name__}
    for image in ("cora-programmer-checks:local", "cora-programmer-frontend:local"):
        try:
            report["checker_images"][image] = {"available": True,
                "id": command(["docker", "image", "inspect", "--format={{.Id}}", image])}
        except ProbeError:
            report["checker_images"][image] = {"available": False}
    for service in ("cora-updater", "pulsante-aggiorna"):
        try:
            report[service] = command(["systemctl", "is-active", service])
        except ProbeError: report[service] = "not_active_or_unavailable"
    try:
        current = json.loads((updater_root / "current.json").read_text())
        config = json.loads((updater_root / "config.json").read_text())
        report["updater"] = {"root": str(updater_root), "active_commit": current.get("commit"),
                             "state_root": config.get("state_root"),
                             "repository": config.get("github_repository"),
                             "branch": config.get("github_branch"),
                             "installed_source_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                                 for name in ("engine.py", "service.py", "check_runner.py")
                                 if (path := updater_root / "installed" / "updater" / name).is_file()}}
        registered = current.get("images", {})
        if registered:
            report["updater"]["registered_images_match"] = all(
                report["services"].get(service, {}).get("image_id") == image
                for service, image in registered.items())
    except (OSError, ValueError): report["updater"] = {"readable": False}
    if api_id:
        try:
            report["api"] = api_probe(api_id, INVENTORY)
        except (ProbeError, ValueError) as error:
            report["api"] = {"error_type": str(error) if isinstance(error, ProbeError) else type(error).__name__}
    state = report.get("updater", {}).get("state_root")
    mounts = report["services"].get("api", {}).get("mounts", [])
    report["workspace_alignment"] = bool(state and report.get("api", {}).get("workspace_root") == "/state/programmer"
        and any(mount.get("Destination") == "/state" and mount.get("Source") == state and mount.get("RW") for mount in mounts)
        and not any(mount.get("Destination") == "/state/programmer" for mount in mounts))
    report["ok"] = (all(row.get("running") and row.get("health") == "healthy" for row in report["services"].values())
                     and report.get("api", {}).get("doctor", {}).get("ok", False)
                     and report.get("api", {}).get("bridge", {}).get("ok", False)
                     and all(row["available"] for row in report["checker_images"].values())
                     and report["cora-updater"] == "active"
                     and bool(report.get("updater", {}).get("active_commit"))
                     and report["workspace_alignment"]
                     and report.get("api", {}).get("workspace_writable", False)
                     and not report.get("api", {}).get("docker_socket_present", True)
                     and report.get("updater", {}).get("registered_images_match", True)
                     and report.get("api", {}).get("bridge", {}).get("commit") == report.get("updater", {}).get("active_commit"))
    return report, api_id


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inspect", "programmer", "ollama", "trace"))
    parser.add_argument("--run-id", help="UUID shown in Attività; required for trace")
    parser.add_argument("--root", type=Path, default=Path("/srv/cora-server-test"))
    parser.add_argument("--compose-file", type=Path, action="append", default=[])
    parser.add_argument("--updater-root", type=Path, default=Path("/srv/cora-tools/updater"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.mode == "trace":
        try: UUID(args.run_id or "")
        except ValueError: parser.error("trace richiede --run-id con UUID valido")
    root = args.root.resolve()
    overrides = [(path if path.is_absolute() else root / path).resolve() for path in args.compose_file]
    report = {"version": 1, "mode": args.mode, "sampled_at": datetime.now(timezone.utc).isoformat()}
    try:
        inventory, api_id = inspect_host(root, overrides, args.updater_root.resolve())
        report["inventory"] = inventory
        if args.mode == "inspect": report["ok"] = inventory["ok"]
        else:
            if not api_id: raise ProbeError("api_not_running")
            source = {"programmer": programmer_source, "ollama": lambda: OLLAMA,
                      "trace": lambda: trace_source(args.run_id)}[args.mode]()
            report["probe"] = api_probe(api_id, source,
                                        timeout=750 if args.mode == "programmer" else 390)
            report["ok"] = inventory["ok"] and report["probe"].get("ok", False)
    except (ProbeError, ValueError, KeyError) as error:
        report.update(ok=False, error_type=str(error) if isinstance(error, ProbeError) else type(error).__name__)
    # Exclusive creation avoids overwriting previous evidence or following symlinks.
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
