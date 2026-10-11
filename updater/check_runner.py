"""Fixed Docker checks, stdlib only; also installed with the trusted host service."""
from __future__ import annotations
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

def _docker(*args: str, timeout: float = 10) -> str:
    # docker logs can be verbose: spool to disk and expose a bounded prefix.
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(["docker", *args], stdout=output, stderr=subprocess.STDOUT, timeout=timeout,
                                check=False, shell=False)
        output.seek(0)
        text = output.read(24000).decode("utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError("Docker non disponibile o verifica non riuscita: " + text[:1000])
    return text.strip()


def run(files, paths, profile, *, checkpoint=lambda: None, docker=_docker, mount=None):
    if profile not in {"python_tests", "typescript", "frontend_build"}:
        raise ValueError("Profilo Docker non consentito.")
    frontend = profile != "python_tests"
    if frontend and not (files / "frontend" / "tsconfig.json").is_file():
        raise ValueError("Configurazione frontend assente nello snapshot.")
    if not frontend and not any(p.startswith("tests/test") and p.endswith(".py") for p in paths):
        raise ValueError("Nessun test Python presente; verifica non eseguita.")
    image = os.getenv("CORA_PROGRAMMER_FRONTEND_CHECK_IMAGE", "cora-programmer-frontend:local") if frontend else os.getenv("CORA_PROGRAMMER_CHECK_IMAGE", "cora-programmer-checks:local")
    # Only fixed commands run; configuration and generated source execute inside isolation.
    script = ("const fs=require('fs'),cp=require('child_process'),crypto=require('crypto');"
              "for(const f of ['package.json','package-lock.json']){const h=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');"
              "if(h('/work/frontend/'+f)!==h('/opt/frontend/'+f))throw new Error('Dependency manifest changed: rebuild trusted check image');}"
              "fs.cpSync('/work/frontend','/tmp/project',{recursive:true});"
              # Own the module root in tmpfs: Vite writes .vite-temp beside its
              # imports. Each installed dependency still points to the read-only
              # image, so only caches/build outputs can be written by the check.
              "fs.mkdirSync('/tmp/project/node_modules');"
              "for(const name of fs.readdirSync('/opt/frontend/node_modules')){"
              "if(name==='.vite'||name==='.vite-temp')continue;"
              "fs.symlinkSync('/opt/frontend/node_modules/'+name,'/tmp/project/node_modules/'+name);}"
              "const r=cp.spawnSync('/opt/frontend/node_modules/.bin/tsc',['-b'],{cwd:'/tmp/project',stdio:'inherit'});"
              "if(r.error)throw r.error;if(r.status!==0)process.exit(r.status??1);")
    if profile == "frontend_build":
        script += "const b=cp.spawnSync('/opt/frontend/node_modules/.bin/vite',['build'],{cwd:'/tmp/project',stdio:'inherit'});if(b.error)throw b.error;process.exit(b.status??1);"
    python_script = ("import shutil,subprocess,sys;"
                     "shutil.copytree('/work','/tmp/project');"
                     "result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-v'],cwd='/tmp/project');"
                     "sys.exit(result.returncode)")
    command = ["--entrypoint=node", image, "-e", script] if frontend else ["--entrypoint=python", image, "-B", "-c", python_script]
    mount = mount or files
    name = "cora-check-" + uuid4().hex
    started = time.monotonic()
    limit = max(1, min(120, float(os.getenv("CORA_PROGRAMMER_CHECK_TIMEOUT_SECONDS", "60"))))
    created = False
    try:
        checkpoint()
        docker("run", "--detach", "--pull=never", "--name", name, "--network=none", "--read-only",
                "--user=65534:65534", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                "--pids-limit=128", "--memory=" + ("1g" if frontend else "512m"), "--cpus=1", "--log-driver=json-file",
                "--log-opt=max-size=1m", "--log-opt=max-file=1",
                "--tmpfs=/tmp:rw,noexec,nosuid,size=" + "256m", "--mount", f"type=bind,src={mount},dst=/work,readonly",
                "--workdir=/work", "--env=PYTHONDONTWRITEBYTECODE=1", "--env=HOME=/tmp",
                *command)
        created = True
        while True:
            checkpoint()
            if time.monotonic() - started > limit:
                raise TimeoutError("Verifica Docker scaduta; container arrestato.")
            running = docker("inspect", "--format={{.State.Running}}", name)
            if running == "false":
                break
            time.sleep(.2)
        code = int(docker("inspect", "--format={{.State.ExitCode}}", name))
        output = docker("logs", "--tail=100", name)
        if profile == "python_tests":
            summary = re.search(r"Ran (\d+) tests?", output)
            skipped = re.search(r"skipped=(\d+)", output)
            if not summary or int(summary[1]) <= (int(skipped[1]) if skipped else 0):
                raise ValueError("Nessun test eseguito riconoscibile; verifica non attestata.")
        return {"profile": profile, "passed": code == 0, "exit_code": code,
                "output": output, "output_may_be_truncated": True, "executes_code": True, "environment": "docker",
                "duration_ms": round((time.monotonic() - started) * 1000)}
    finally:
        # Do not report success if cleanup fails: the container might still run.
        if created:
            docker("rm", "--force", name)
        else:
            try:
                docker("rm", "--force", name)
            except RuntimeError:
                pass
