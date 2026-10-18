"""Prepare a checked Windows candidate without replacing the running installation."""
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import threading
from urllib.request import Request, urlopen
import zipfile
from fastapi import APIRouter, HTTPException
from core.auth import auth_mode

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "Aleselva12/serveria1"
router = APIRouter(prefix="/api/v1/system/update", tags=["Aggiornamenti"])
LOCK = threading.Lock()
JOB = {"status": "idle"}
LIMIT = 60 * 1024 * 1024
WINDOWS_TESTS = (
    "tests.test_ollama_tool_arguments",
    "tests.test_programmer_loop_context",
    "tests.test_desktop_auth_update", "tests.test_programmer_response_recovery",
    "tests.test_programmer_context", "tests.test_tailscale_auth.TailscaleAuthTests",
    "tests.test_programmer_router", "tests.test_generation_policy", "tests.test_core_protocol",
)


def desktop():
    return auth_mode() == "desktop" and sys.platform == "win32"


def server_url():
    from urllib.parse import urlsplit
    value = os.getenv("CORA_UPDATE_URL", "").strip()
    parsed = urlsplit(value)
    if value and (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password):
        raise HTTPException(503, "CORA_UPDATE_URL deve essere un indirizzo HTTPS senza credenziali.")
    return value


@router.get("")
def status():
    if desktop():
        with LOCK:
            return {"platform": "windows", **JOB}
    return {"platform": "server", "url": server_url(), "status": "configured" if server_url() else "unconfigured"}


def extract_candidate(data, destination):
    """Reject traversal, links, duplicate names and decompression bombs before writing."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 10000 or sum(x.file_size for x in entries) > 200 * 1024 * 1024:
            raise ValueError("Archivio oltre i limiti.")
        names = set()
        for entry in entries:
            parts = PurePosixPath(entry.filename).parts
            if (not parts or entry.filename.startswith("/") or "\\" in entry.filename
                    or any(p in {".", ".."} or ":" in p or p.endswith((".", " "))
                           or p.split(".", 1)[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1,10)], *[f"LPT{i}" for i in range(1,10)]}
                           for p in parts)
                    or ((entry.external_attr >> 16) & 0o170000) == 0o120000):
                raise ValueError("Percorso archivio non valido.")
            relative = Path(*parts[1:])
            if len(parts) == 1:
                continue
            # Only source is accepted. Upstream archives cannot supply local state.
            if parts[1] in {"data", "state", ".venv", "node_modules", ".env", ".git"}:
                raise ValueError("Stato privato presente nell'archivio.")
            key = str(relative).casefold()
            if key in names:
                raise ValueError("Percorso duplicato nell'archivio.")
            names.add(key)
        for entry in entries:
            parts = PurePosixPath(entry.filename).parts[1:]
            if not parts:
                continue
            target = destination.joinpath(*parts)
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
    if not all((destination / p).is_file() for p in ("AVVIO.cmd", "requirements-test.txt", "frontend/package-lock.json")):
        raise ValueError("Archivio Cora incompleto.")


def download(url):
    with urlopen(Request(url, headers={"User-Agent": "Cora-updater"}), timeout=30) as response:
        data = response.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError("Download oltre i limiti.")
    return data


def check(command, cwd, environment):
    result = subprocess.run(command, cwd=cwd, env=environment, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=900, check=False)
    with (cwd / "update-checks.log").open("ab") as stream:
        stream.write(result.stdout)
    if result.returncode:
        raise ValueError("Controllo candidato fallito.")


def prepare():
    candidate = None
    phase = "download"
    try:
        commit = json.loads(download(f"https://api.github.com/repos/{REPOSITORY}/commits/main"))["sha"]
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Commit non valido.")
        import tempfile
        parent = ROOT.parent / (ROOT.name + "-updates")
        parent.mkdir(exist_ok=True)
        candidate = Path(tempfile.mkdtemp(prefix=commit[:12] + "-", dir=parent))
        extract_candidate(download(f"https://codeload.github.com/{REPOSITORY}/zip/{commit}"), candidate)
        phase = "tests"
        environment = {k:v for k,v in os.environ.items() if not k.startswith(("CORA_", "PG", "OLLAMA_"))}
        environment.update(CORA_DATABASE_URL="", CORA_AUTH_MODE="password")
        # Tests use the running installation's interpreter; no production database or state.
        check([sys.executable, "-m", "unittest", *WINDOWS_TESTS], candidate, environment)
        npm = shutil.which("npm.cmd")
        if not npm:
            raise ValueError("Node.js/npm non disponibile.")
        for args in (("ci", "--include=dev"), ("test",), ("run", "build")):
            check([npm, *args], candidate / "frontend", environment)
        phase = "ready"
        # State stays at its original path. The owner switches only after stopping Cora
        # and backing up PostgreSQL; never activate code from a background HTTP worker.
        quote = lambda p: "'" + str(p).replace("'", "''") + "'"
        script = "$ErrorActionPreference = 'Stop'\n"
        script += "if (Get-NetTCPConnection -LocalPort 8000,5173 -State Listen -ErrorAction SilentlyContinue) { throw 'Chiudi Cora prima di continuare.' }\n"
        script += f"Copy-Item -LiteralPath {quote(ROOT / '.env')} -Destination {quote(candidate / '.env')}\n"
        script += f"New-Item -ItemType Junction -Path {quote(candidate / 'data')} -Target {quote(ROOT / 'data')} | Out-Null\n"
        script += f"& {quote(candidate / 'AVVIO.ps1')}\n"
        (candidate / "ATTIVA.ps1").write_text(script, encoding="utf-8-sig")
        with LOCK:
            JOB.update(status="ready", commit=commit, directory=str(candidate), phase=phase)
    except Exception as error:
        with LOCK:
            JOB.update(status="failed", phase=phase, error_type=type(error).__name__,
                       directory=str(candidate) if candidate else "")


@router.post("/prepare", status_code=202)
def start():
    if not desktop():
        raise HTTPException(409, "Sul server usa il servizio aggiornamenti Debian configurato.")
    with LOCK:
        if JOB["status"] == "running":
            raise HTTPException(409, "Preparazione già in corso: controlla lo stato.")
        JOB.clear()
        JOB.update(status="running")
        threading.Thread(target=prepare, daemon=True).start()
        return dict(JOB)
