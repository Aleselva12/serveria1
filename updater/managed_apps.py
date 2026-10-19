"""Allowlisted host app updater. Runs on the Debian host, not in Cora agents."""
from pathlib import Path
import os
import subprocess
import threading

CATALOG = {
    "magazzino-tele": {
        "name": "Magazzino Tele",
        "repository": "https://github.com/Aleselva12/magazzino-tele.git",
        "branch": "master",
        "compose": "deploy/compose.yml",
        "web_url": "http://serverale.tail7b83c3.ts.net:8082/",
    }
}
BUSY = {"running"}

class AppManager:
    def __init__(self, config):
        self.root = Path(config.get("managed_apps_root", "/srv/apps")).resolve()
        self.lock = threading.Lock()
        self.jobs = {}
        self.enabled = config.get("managed_apps_enabled") is True

    def path(self, key):
        if key not in CATALOG:
            raise ValueError("Applicazione non autorizzata")
        return self.root / key

    def _run(self, command, cwd=None, timeout=300):
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                timeout=timeout, check=False,
                                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        if result.returncode != 0:
            raise RuntimeError("Comando di manutenzione terminato con codice " + str(result.returncode))
        return result.stdout.strip()

    def _compose(self, folder, item, *args, timeout=120):
        return self._run(["docker", "compose", "--env-file", "deploy/.env",
                          "-f", item["compose"], *args], cwd=folder, timeout=timeout)

    def _status_one(self, key, item):
        folder = self.path(key)
        installed = (folder / ".git").is_dir() and (folder / item["compose"]).is_file()
        configured = installed and (folder / "deploy/.env").is_file() and (folder / "deploy/init/01-schema.sql").is_file()
        commit = None
        running = False
        if installed:
            try:
                commit = self._run(["git", "rev-parse", "--short", "HEAD"], cwd=folder, timeout=8)
            except (RuntimeError, OSError, subprocess.TimeoutExpired):
                pass
        if configured:
            try:
                ident = self._compose(folder, item, "ps", "-q", "web", timeout=12).strip()
                if ident:
                    status = self._run(["docker", "inspect", "--format", "{{.State.Status}}", ident], timeout=10)
                    health = self._run(["docker", "inspect", "--format",
                                        "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", ident], timeout=10)
                    running = status == "running" and health in ("healthy", "none")
            except (RuntimeError, OSError, subprocess.TimeoutExpired):
                pass
        job = self.jobs.get(key, {"status": "idle"})
        return {"id": key, "name": item["name"], "repository": item["repository"],
                "installed": installed, "configured": configured, "running": running,
                "commit": commit, "job": dict(job),
                "url": item["web_url"] if running else None}

    def status(self):
        return {"available": self.enabled,
                "apps": [self._status_one(key, item) for key, item in CATALOG.items()]}

    def submit(self, key, action):
        if not self.enabled:
            raise ValueError("Gestione applicazioni non abilitata sul servizio host")
        if action not in {"install", "update"}:
            raise ValueError("Azione non autorizzata")
        self.path(key)
        if not self.lock.acquire(blocking=False):
            raise ValueError("Un'operazione è già in corso")
        self.jobs[key] = {"status": "running", "phase": "queued", "action": action}
        threading.Thread(target=self._work, args=(key, action), daemon=True).start()
        return dict(self.jobs[key])

    def _work(self, key, action):
        item = CATALOG[key]
        folder = self.path(key)
        phase = "checkout"
        try:
            self.jobs[key] = {"status": "running", "phase": phase, "action": action}
            if action == "install":
                if folder.exists():
                    raise ValueError("Directory già presente: usare Aggiorna")
                if not self.root.is_dir() or self.root.is_symlink():
                    raise ValueError("Directory applicazioni non predisposta")
                self._run(["git", "clone", "--single-branch", "--branch",
                           item["branch"], item["repository"], str(folder)], timeout=300)
            else:
                if not (folder / ".git").is_dir():
                    raise ValueError("Sorgenti non installati")
                # Do not overwrite local tracked changes.
                if self._run(["git", "status", "--porcelain"], cwd=folder):
                    raise ValueError("File locali modificati: aggiornamento sospeso")
                self._run(["git", "fetch", "origin", item["branch"]], cwd=folder)
                self._run(["git", "merge", "--ff-only", "FETCH_HEAD"], cwd=folder)
            if not (folder / item["compose"]).is_file():
                raise ValueError("File Compose non presente")
            if not (folder / "deploy/.env").is_file() or not (folder / "deploy/init/01-schema.sql").is_file():
                self.jobs[key] = {"status": "needs_configuration", "action": action,
                                  "phase": "setup"}
                return
            phase = "validate"
            self.jobs[key] = {"status": "running", "phase": phase, "action": action}
            self._compose(folder, item, "config", "--quiet")
            phase = "deploy"
            self.jobs[key] = {"status": "running", "phase": phase, "action": action}
            self._compose(folder, item, "up", "-d", "--build", "--wait", timeout=1200)
            phase = "verify"
            self.jobs[key] = {"status": "running", "phase": phase, "action": action}
            current = self._status_one(key, item)
            if not current["running"]:
                raise RuntimeError("Web non healthy dopo il deployment")
            self.jobs[key] = {"status": "completed", "phase": "ready", "action": action}
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as err:
            self.jobs[key] = {"status": "failed", "phase": phase, "action": action,
                              "message": str(err) if isinstance(err, ValueError) else
                              "Problema nel deployment: controllare i log Docker"}
        finally:
            self.lock.release()
