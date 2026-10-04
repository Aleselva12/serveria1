"""Static checks never execute generated source; test execution is Docker-only."""
from __future__ import annotations
import ast
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4
from core.runtime import checkpoint
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


def docker_check(identifier: str) -> dict:
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
    image = os.getenv("CORA_PROGRAMMER_CHECK_IMAGE", "cora-programmer-checks:local")
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
                "--pids-limit=128", "--memory=512m", "--cpus=1", "--log-driver=json-file",
                "--log-opt=max-size=1m", "--log-opt=max-file=1",
                "--tmpfs=/tmp:rw,noexec,nosuid,size=64m", "--mount", f"type=bind,src={mount},dst=/work,readonly",
                "--workdir=/work", "--env=PYTHONDONTWRITEBYTECODE=1", "--env=HOME=/tmp",
                "--entrypoint=python", image, "-B", "-m", "unittest", "discover", "-s", "tests", "-v")
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
        return {"profile": "python_tests", "passed": code == 0, "exit_code": code,
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
    elif profile == "python_tests":
        result = docker_check(identifier)
    else:
        raise ValueError("Profilo consentito: syntax o python_tests.")
    ws._atomic(ws.directory(identifier) / "last_check.json", json.dumps(result, ensure_ascii=False))
    return result


def run_check(identifier: str, profile: str = "syntax") -> dict:
    # File mutations through Cora cannot change a test's source while it runs.
    with ws.LOCK:
        return _run_check(identifier, profile)
