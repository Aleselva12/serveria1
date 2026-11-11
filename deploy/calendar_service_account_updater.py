"""Install or reconcile Calendar's read-only service-account bind in updater snapshot.

Owner-only host operation. Never copies or prints the private key.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path

TARGET = "/run/cora-secrets/cora-calendar.json"
PATH_VARIABLE = "CORA_GOOGLE_CALENDAR_SERVICE_ACCOUNT_PATH"
ID_VARIABLE = "CORA_GOOGLE_CALENDAR_ID"


def read_calendar_id(env_file: Path) -> str:
    """Read only Calendar ID from the private deploy file."""
    if env_file.is_symlink() or not env_file.is_file():
        raise ValueError("deploy.env non disponibile o link simbolico")
    values = []
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(ID_VARIABLE + "="):
            values.append(line.split("=", 1)[1].strip().strip("\\\"'"))
    if len(values) != 1 or not values[0] or values[0] == "primary":
        raise ValueError("Inserisci un solo ID calendario condiviso in deploy.env (non 'primary')")
    if (any(c.isspace() for c in values[0]) or len(values[0]) > 512
            or "://" in values[0] or "/" in values[0] or "?" in values[0]):
        raise ValueError("ID calendario non valido")
    return values[0]


def check_key(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError("File JSON Service Account assente o link simbolico")
    if path.stat().st_mode & 0o077:
        raise ValueError("La chiave deve avere permessi riservati (es. chmod 600)")
    with path.open(encoding="utf-8") as f:
        info = json.load(f)
    if info.get("type") != "service_account" or not info.get("client_email") or not info.get("private_key"):
        raise ValueError("Credenziali Service Account incomplete")


def configure(snapshot: dict, *, source: str, calendar_id: str) -> dict:
    """Pure transform; preserve every unrelated service, environment key and bind."""
    candidate = copy.deepcopy(snapshot)
    api = candidate["services"]["api"]
    env = api["environment"]
    if not isinstance(env, dict):
        raise ValueError("Formato environment API non supportato")
    volumes = api.setdefault("volumes", [])
    for volume in volumes:
        if not isinstance(volume, dict):
            raise ValueError("Formato volume API non supportato")
        if volume.get("target") == TARGET and (
            volume.get("source") != source or volume.get("read_only") is not True
        ):
            raise ValueError("Mount Calendar esistente diverso: rivedere manualmente")
        if volume.get("source") == source and volume.get("target") != TARGET:
            raise ValueError("La stessa chiave è montata in una posizione inattesa")
    if not any(item.get("target") == TARGET for item in volumes):
        volumes.append({
            "type": "bind", "source": source, "target": TARGET,
            "read_only": True, "bind": {"create_host_path": False},
        })
    env[PATH_VARIABLE] = TARGET
    env[ID_VARIABLE] = calendar_id
    return candidate


def apply(root: Path, env_file: Path, key: Path, *, verify=True) -> str:
    root = root.resolve()
    snapshot_file = root / "compose.json"
    images = root / "images.json"
    if any(p.is_symlink() or not p.is_file() for p in (snapshot_file, images)):
        raise ValueError("Updater snapshot/images mancanti o non validi")
    for job in (root / "jobs").glob("*/job.json"):
        if json.loads(job.read_text()).get("status") in {"queued", "running", "recovery_required"}:
            raise ValueError("Job updater attivo: operazione rifiutata")

    key = key.absolute()
    check_key(key)
    calendar_id = read_calendar_id(env_file)
    original = snapshot_file.read_bytes()
    image_original = images.read_bytes()
    candidate = configure(json.loads(original), source=str(key), calendar_id=calendar_id)
    if candidate == json.loads(original):
        return "already-configured"

    with tempfile.TemporaryDirectory(prefix=".calendar-config-", dir=root) as folder:
        pending = Path(folder) / "compose.json"
        pending.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
        pending.chmod(0o600)
        if verify:
            subprocess.run(
                ["docker", "compose", "-p", candidate.get("name", "cora"),
                 "-f", str(pending), "-f", str(images), "config", "--quiet"],
                check=True, stdout=subprocess.DEVNULL,
            )
        if snapshot_file.read_bytes() != original or images.read_bytes() != image_original:
            raise ValueError("Snapshot updater cambiato durante la verifica")
        backup = root / ("compose.before-calendar-" + secrets.token_hex(8) + ".json")
        with backup.open("xb") as f:
            f.write(original)
            f.flush()
            os.fsync(f.fileno())
        backup.chmod(0o600)
        os.replace(pending, snapshot_file)
    return str(backup)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--updater-root", type=Path, default=Path("/srv/cora-tools/updater"))
    parser.add_argument("--deploy-env", type=Path, required=True)
    parser.add_argument("--key", type=Path, default=Path("/srv/cora-secrets/cora-calendar.json"))
    parser.add_argument("--apply", action="store_true", help="Scrive lo snapshot solo dopo il controllo Docker")
    args = parser.parse_args()
    calendar_id = read_calendar_id(args.deploy_env)
    check_key(args.key)
    snapshot = args.updater_root / "compose.json"
    if snapshot.is_symlink() or not snapshot.is_file():
        raise SystemExit("Snapshot updater mancante o link simbolico")
    candidate = configure(json.loads(snapshot.read_text()), source=str(args.key.absolute()),
                          calendar_id=calendar_id)
    current = json.loads(snapshot.read_text())
    print("Configurazione Calendar:", "già presente" if candidate == current else "da installare")
    if not args.apply:
        print("Solo verifica; nessuna modifica. Per applicare: --apply a updater fermo.")
        return
    result = subprocess.run(["systemctl", "is-active", "--quiet", "cora-updater.service"], check=False)
    if result.returncode == 0:
        raise SystemExit("Ferma prima cora-updater.service per evitare modifiche concorrenti.")
    backup = apply(args.updater_root, args.deploy_env, args.key)
    print("Snapshot aggiornato." if backup != "already-configured" else "Snapshot già configurato.")
    if backup != "already-configured":
        print("Backup:", backup)
        print("Riavvia l'updater, poi ricrea solo api con compose.json + images.json; verifica Calendar.")
    # Intentionally does not recreate containers or print private configuration.


if __name__ == "__main__":
    main()
