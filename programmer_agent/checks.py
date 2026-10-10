"""Static checks never execute generated source; test execution is Docker-only."""
from __future__ import annotations
import ast
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4
from core.runtime import checkpoint, RunStopped
from programmer_agent import workspace as ws


def static_check(identifier: str) -> dict:
    errors = []
    checked = 0
    for relative in ws.list_files(identifier):
        checkpoint()
        path = ws.file_path(identifier, relative)
        if path.suffix not in {".py", ".json"}:
            continue
        checked += 1
        try:
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".py":
                ast.parse(text, filename=relative)
            else:
                json.loads(text)
        except (SyntaxError, ValueError) as error:
            errors.append({"path": relative, "line": getattr(error, "lineno", None), "error": str(error)[:300]})
    if checked == 0:
        errors.append({"path": "", "error": "Nessun file Python o JSON: controllo di sintassi non applicabile."})
    return {"profile": "syntax", "passed": not errors, "checked": checked, "errors": errors[:50],
            "total_errors": len(errors), "executes_code": False,
            "scope": "Sintassi Python e JSON; non verifica import, tipi, build o comportamento."}


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


def docker_check(identifier: str, profile: str = "python_tests") -> dict:
    if not shutil.which("docker"):
        raise ValueError("Docker non disponibile. Le verifiche statiche restano utilizzabili.")
    files = ws.directory(identifier) / "files"
    paths = ws.list_files(identifier)
    # Refuse unvalidated filesystem entries, including links produced outside Cora.
    for folder, dirs, names in os.walk(files, followlinks=False):
        for name in dirs + names:
            ws._no_links(Path(folder) / name)
    for relative in paths:
        ws.file_path(identifier, relative)
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
              "fs.symlinkSync('/opt/frontend/node_modules','/tmp/project/node_modules','dir');"
              "const r=cp.spawnSync('/opt/frontend/node_modules/.bin/tsc',['-b'],{cwd:'/tmp/project',stdio:'inherit'});"
              "if(r.error)throw r.error;if(r.status!==0)process.exit(r.status??1);")
    if profile == "frontend_build":
        script += "const b=cp.spawnSync('/opt/frontend/node_modules/.bin/vite',['build'],{cwd:'/tmp/project',stdio:'inherit'});if(b.error)throw b.error;process.exit(b.status??1);"
    python_script = ("import shutil,subprocess,sys;"
                     "shutil.copytree('/work','/tmp/project');"
                     "result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-v'],cwd='/tmp/project');"
                     "sys.exit(result.returncode)")
    command = ["--entrypoint=node", image, "-e", script] if frontend else ["--entrypoint=python", image, "-B", "-c", python_script]
    host_root = os.getenv("CORA_PROGRAMMER_DOCKER_WORKSPACE_ROOT", "")
    mount = Path(host_root) / identifier / "files" if host_root else files
    name = "cora-check-" + uuid4().hex
    started = time.monotonic()
    limit = max(1, min(120, float(os.getenv("CORA_PROGRAMMER_CHECK_TIMEOUT_SECONDS", "60"))))
    created = False
    try:
        checkpoint()
        _docker("run", "--detach", "--pull=never", "--name", name, "--network=none", "--read-only",
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
            running = _docker("inspect", "--format={{.State.Running}}", name)
            if running == "false":
                break
            time.sleep(.2)
        code = int(_docker("inspect", "--format={{.State.ExitCode}}", name))
        output = _docker("logs", "--tail=100", name)
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
            _docker("rm", "--force", name)
        else:
            try:
                _docker("rm", "--force", name)
            except RuntimeError:
                pass


def _run_check(identifier: str, profile: str = "syntax") -> dict:
    if profile == "syntax":
        result = static_check(identifier)
    elif profile == "contracts":
        from programmer_agent.contract_checks import contracts
        result = contracts(identifier)
    elif profile in {"python_tests", "typescript", "frontend_build"}:
        result = docker_check(identifier, profile)
    else:
        raise ValueError("Profilo consentito: syntax, contracts, python_tests, typescript o frontend_build.")
    return result


def _record_check(identifier: str, result: dict) -> dict:
    from programmer_agent.components import check_history, workspace_digest, now
    result.update(workspace_digest=workspace_digest(identifier), checked_at=now())
    history = check_history(identifier)
    history.append(result)
    ws._atomic(ws.directory(identifier) / "checks.json", json.dumps(history[-50:], ensure_ascii=False))
    ws._atomic(ws.directory(identifier) / "last_check.json", json.dumps(result, ensure_ascii=False))
    return result


def run_check(identifier: str, profile: str = "syntax") -> dict:
    # File mutations through Cora cannot change a test's source while it runs.
    if profile not in {"syntax", "contracts", "python_tests", "typescript", "frontend_build"}:
        raise ValueError("Profilo non consentito.")
    with ws.LOCK:
        from programmer_agent.components import workspace_digest
        before = workspace_digest(identifier)
        try:
            result = _run_check(identifier, profile)
            if workspace_digest(identifier) != before:
                raise ws.WorkspaceConflict("Workspace cambiato durante la verifica: risultato non attestato.")
        except RunStopped:
            _record_check(identifier, {"profile": profile, "passed": False, "completed": False,
                                      "error": "Verifica interrotta.", "scope": "Verifica non completata."})
            raise
        except (ValueError, OSError, RuntimeError, TimeoutError) as error:
            _record_check(identifier, {"profile": profile, "passed": False, "completed": False,
                                      "error": str(error)[:1000], "scope": "Verifica non completata."})
            raise
        return _record_check(identifier, result)
