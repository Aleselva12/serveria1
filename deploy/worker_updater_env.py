"""Synchronize private worker connectivity settings with the updater's frozen Compose snapshot.

Run only on the Debian host, with cora-updater stopped and no release job active.
This does not modify other services, mounts, images, or published ports.
No secrets are printed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import uuid
from pathlib import Path

KEYS = ("CORA_WORKER_SHARED_TOKEN", "CORA_TAILSCALE_DNS_SUFFIX")


def read_settings(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name in KEYS:
            if name in values:
                raise ValueError("Variabile duplicata in deploy.env: " + name)
            values[name] = value.strip().strip('"').strip("'")
    if len(values.get("CORA_WORKER_SHARED_TOKEN", "")) < 32:
        raise ValueError("Token worker assente o troppo corto nel deploy.env")
    suffix = values.get("CORA_TAILSCALE_DNS_SUFFIX", "")
    if not re.fullmatch(r"[a-z0-9-]+\.ts\.net", suffix) or suffix.startswith("-"):
        raise ValueError("CORA_TAILSCALE_DNS_SUFFIX non valido")
    return values


def synchronize(root: Path, deploy: Path, apply: bool = False) -> tuple[bool, Path | None]:
    root = root.resolve()
    if root.is_symlink():
        raise ValueError("Percorso updater non valido")
    file = root / "compose.json"
    if not file.is_file() or file.is_symlink():
        raise ValueError("Snapshot updater compose.json non disponibile")
    if not deploy.is_file() or deploy.is_symlink():
        raise ValueError("deploy.env non disponibile")
    desired = read_settings(deploy)
    original = file.read_bytes()
    config = json.loads(original)
    if not isinstance(config, dict) or not isinstance(config.get("services"), dict):
        raise ValueError("Snapshot Compose non valido")
    api = config["services"].get("api")
    if not isinstance(api, dict):
        raise ValueError("API Cora non disponibile nello snapshot")
    env = api.get("environment")
    if not isinstance(env, dict):
        raise ValueError("Environment API non riconosciuto: intervento manuale richiesto")
    change = any(env.get(key) != desired[key] for key in KEYS)
    if not apply or not change:
        return change, None

    env.update({key: desired[key] for key in KEYS})
    backup = root / ("compose.before-worker-" + uuid.uuid4().hex + ".json")
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(original)
        stream.flush()
        os.fsync(stream.fileno())

    fd, tmp = tempfile.mkstemp(prefix=".compose-worker-", dir=root)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(config, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, file)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return True, backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--updater-root", default="/srv/cora-tools/updater")
    parser.add_argument("--deploy-env", default="/srv/cora-server-test/deploy.env")
    parser.add_argument("--apply", action="store_true",
                        help="Write the updater snapshot. Stop cora-updater first.")
    args = parser.parse_args()
    if args.apply:
        import subprocess
        result = subprocess.run(["systemctl", "is-active", "--quiet", "cora-updater"],
                                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            raise SystemExit("Ferma cora-updater prima di aggiornare lo snapshot.")
    changed, backup = synchronize(Path(args.updater_root), Path(args.deploy_env), args.apply)
    if not args.apply:
        print("Snapshot updater da aggiornare:", changed)
    else:
        print("Snapshot aggiornato:", changed)
        if backup:
            print("Backup privato dello snapshot:", backup)
        print("Nessun container riavviato. Usa il Compose attivo per ricreare soltanto api.")


if __name__ == "__main__":
    main()
