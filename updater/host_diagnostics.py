"""Read-only diagnostics for the Debian host running the updater.

Only fixed, allowlisted observations are exposed. No arbitrary command, file
content, environment value, credential or journal line is returned.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

SERVICES = ("cora-updater.service", "ssh.service")
SYSTEMD_PROPERTIES = (
    "LoadState", "ActiveState", "SubState", "UnitFileState",
    "ExecMainStatus", "NRestarts", "FragmentPath", "StandardOutput", "StandardError",
)


def _run(command: list[str], *, timeout: int = 5) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def _systemd_unit(name: str) -> dict[str, Any]:
    if name not in SERVICES:
        raise ValueError("Unità non autorizzata")
    if not shutil.which("systemctl"):
        return {"available": False, "reason": "systemctl non disponibile"}
    command = ["systemctl", "show", name]
    for key in SYSTEMD_PROPERTIES:
        command += ["--property", key]
    result = _run(command)
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if key in SYSTEMD_PROPERTIES:
                values[key] = value
    return {
        "available": result.returncode == 0 and bool(values),
        "loadState": values.get("LoadState", ""),
        "activeState": values.get("ActiveState", ""),
        "subState": values.get("SubState", ""),
        "unitFileState": values.get("UnitFileState", ""),
        "execMainStatus": values.get("ExecMainStatus", ""),
        "restarts": values.get("NRestarts", ""),
        "fragmentPresent": bool(values.get("FragmentPath")),
        "standardOutput": values.get("StandardOutput", ""),
        "standardError": values.get("StandardError", ""),
    }


def _safe_mode(path: Path) -> dict[str, Any]:
    try:
        info = path.stat()
    except OSError:
        return {"exists": False}
    return {
        "exists": True,
        "mode": stat.S_IMODE(info.st_mode),
        "ownerUid": info.st_uid,
        "ownerGid": info.st_gid,
    }


def _os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key in {"ID", "VERSION_ID", "VERSION_CODENAME", "PRETTY_NAME"}:
                values[key] = value.strip().strip('"')
    except OSError:
        pass
    return values


def _dpkg_status() -> dict[str, Any]:
    if not shutil.which("dpkg"):
        return {"available": False, "auditClean": False}
    audit = _run(["dpkg", "--audit"], timeout=15)
    return {
        "available": True,
        "auditClean": audit.returncode == 0 and not audit.stdout.strip(),
    }


def _upgrade_status() -> dict[str, Any]:
    """Read cached APT metadata only; never runs apt update or installs packages."""
    if not shutil.which("apt-get"):
        return {"available": False, "pending": None}
    result = _run(["apt-get", "-s", "-o", "Debug::NoLocking=1", "upgrade"], timeout=30)
    if result.returncode != 0:
        return {"available": True, "pending": None, "simulationOk": False}
    pending = sum(1 for line in result.stdout.splitlines() if line.startswith("Inst "))
    return {"available": True, "pending": pending, "simulationOk": True}


def _auto_security_updates(conf_dir: Path = Path("/etc/apt/apt.conf.d")) -> dict[str, bool]:
    """Booleans only: is unattended-upgrades installed and enabled by APT::Periodic."""
    enabled = False
    try:
        for path in sorted(conf_dir.iterdir()):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                line = line.split("//", 1)[0].strip()
                if line.startswith("APT::Periodic::Unattended-Upgrade"):
                    enabled = '"0"' not in line and '"' in line
    except OSError:
        pass
    return {"installed": bool(shutil.which("unattended-upgrade")), "enabled": enabled}


def inspect(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    root = Path(root).resolve()
    uid = os.getuid() if hasattr(os, "getuid") else None
    gid = os.getgid() if hasattr(os, "getgid") else None
    configured_uid = config.get("uid")
    configured_gid = config.get("gid")
    token = _safe_mode(root / "bridge.token")
    config_file = _safe_mode(root / "config.json")
    private_files_ok = all(
        item.get("exists") and item.get("mode", 0o777) & 0o077 == 0
        for item in (token, config_file)
    )
    identity_ok = (
        uid is not None and gid is not None and
        configured_uid == uid and configured_gid == gid
    )
    units = {name: _systemd_unit(name) for name in SERVICES}
    return {
        "schema": 1,
        "os": _os_release(),
        "identity": {
            "uidMatchesConfigured": identity_ok,
            "privateUpdaterFiles": private_files_ok,
        },
        "packages": {
            "dpkg": _dpkg_status(),
            "upgrades": _upgrade_status(),
            "autoSecurityUpdates": _auto_security_updates(),
        },
        "systemd": units,
        "scope": (
            "Read-only host evidence: Debian identity, updater UID/GID and private "
            "file modes, dpkg audit, cached APT upgrade simulation, automatic security "
            "update flags, and fixed "
            "systemd units. No restart, update, SSH login or journal content."
        ),
    }
