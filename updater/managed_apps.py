"""Fixed allowlist for separately deployed apps; never executes from model input."""
import json
import os
from pathlib import Path
import subprocess
import threading

CATALOG = {
    "magazzino-tele": {
        "name": "Magazzino Tele",
        "repository": "https://github.com/Aleselva12/magazzino-tele.git",
        "branch": "master",
        "compose": "deploy/compose.yml",
        "web_url": "http://100.112.253.3:8082",
    }
}

class AppManager:
    def __init__(self, config):
        self.config = config
        self.root = Path(config.get("managed_apps_root", "/srv/apps")).resolve()
        self.lock = threading.Lock()
        self.jobs = {}
        self.enabled = bool(config.get("managed_apps_enabled", False))

    def path(self, key):
        if key not in CATALOG:
            raise ValueError("Applicazione non autorizzata")
        return self.root/key

    def _run(self, args, cwd=None, timeout=300):
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        if p.returncode:
            raise RuntimeError("Operazione host fallita (codice "+str(p.returncode)+")")

    def status(self):
        result=[]
        for key, item in CATALOG.items():
            folder=self.path(key)
            installed=(folder/".git").is_dir() and (folder/item["compose"]).is_file()
            result.append({"id":key,"name":item["name"],"repository":item["repository"],
                           "installed":installed,"job":self.jobs.get(key,{"status":"idle"}),
                           "url":item["web_url"] if installed else None})
        return {"available":self.enabled,"apps":result}

    def submit(self, key, action):
        if not self.enabled:
            raise ValueError("Gestione applicazioni non abilitata sul servizio host")
        if action not in {"install","update"}:
            raise ValueError("Azione non supportata")
        self.path(key)
        if not self.lock.acquire(blocking=False):
            raise ValueError("Un'operazione sulle applicazioni è già in corso")
        self.jobs[key]={"status":"running","action":action}
        threading.Thread(target=self._work, args=(key,action), daemon=True).start()
        return dict(self.jobs[key])

    def _work(self,key,action):
        item=CATALOG[key]
        folder=self.path(key)
        try:
            # Admin provisions /srv/apps and .env privately. A fresh install clones
            # sources ONLY: activation is explicitly gated by host .env and schema.
            if action=="install":
                if folder.exists(): raise ValueError("La directory esiste già: installazione interrotta")
                if not self.root.is_dir() or self.root.is_symlink():
                    raise ValueError("Directory delle applicazioni non predisposta")
                self._run(["git","clone","--single-branch","--branch",item["branch"],
                           item["repository"],str(folder)],timeout=300)
                if not (folder/item["compose"]).is_file():
                    raise ValueError("Compose assente nel repository")
            else:
                if not (folder/".git").is_dir() or not (folder/item["compose"]).is_file():
                    raise ValueError("Applicazione non installata")
                self._run(["git","fetch","--ff-only","origin",item["branch"]],cwd=folder)
                self._run(["git","merge","--ff-only","FETCH_HEAD"],cwd=folder)
            # Never touch a live database without explicit host provisioning.
            if not (folder/"deploy"/".env").is_file() or not (folder/"deploy"/"init"/"01-schema.sql").is_file():
                self.jobs[key]={"status":"needs_configuration","action":action}
                return
            self._run(["docker","compose","--env-file","deploy/.env","-f",item["compose"],
                       "config","--quiet"],cwd=folder,timeout=120)
            # Install/update runs only the exact allowlisted Compose, not arbitrary repo.
            self._run(["docker","compose","--env-file","deploy/.env","-f",item["compose"],
                       "up","-d","--build"],cwd=folder,timeout=1200)
            self.jobs[key]={"status":"completed","action":action}
        except Exception:
            self.jobs[key]={"status":"failed","action":action,
                            "message":"Controlla configurazione e log del servizio host"}
        finally:
            self.lock.release()
