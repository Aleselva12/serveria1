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


# Shared runner retains the same isolation policy in local development and on host.
from updater.check_runner import _docker, run as run_docker


def docker_check(identifier: str, profile: str = "python_tests") -> dict:
    if profile not in {"python_tests", "typescript", "frontend_build"}:
        raise ValueError("Profilo Docker non consentito.")
    if os.getenv("CORA_UPDATER_URL"):
        from programmer_agent.releases import request
        from programmer_agent.components import workspace_digest
        checkpoint()
        result = request("POST", "/workspaces/" + identifier + "/check",
                         {"profile": profile, "workspace_digest": workspace_digest(identifier)}, timeout=180)
        checkpoint()
        return result
    if not shutil.which("docker"):
        raise ValueError("Verifiche Docker: configura il servizio host secondo updater/README.md. Sintassi e contratti restano disponibili.")
    files = ws.directory(identifier) / "files"
    paths = ws.list_files(identifier)
    for folder, dirs, names in os.walk(files, followlinks=False):
        for name in dirs + names:
            ws._no_links(Path(folder) / name)
    for relative in paths:
        ws.file_path(identifier, relative)
    host_root = os.getenv("CORA_PROGRAMMER_DOCKER_WORKSPACE_ROOT", "")
    mount = Path(host_root) / identifier / "files" if host_root else files
    return run_docker(files, paths, profile, checkpoint=checkpoint, docker=_docker, mount=mount)


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
