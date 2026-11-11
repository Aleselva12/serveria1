"""Revision of the tested code, never borrowed from the updater's current pointer."""
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def revision() -> str:
    try:
        value = (ROOT / ".cora-revision").read_text().strip()
    except OSError:
        value = os.getenv("CORA_GIT_COMMIT", "").strip()
    if re.fullmatch(r"[a-fA-F0-9]{40}", value):
        return value.lower()
    # Older host updaters do not pass the Docker build argument. Their git
    # archive still embeds the exact source commit through export-subst.
    # The literal placeholder in a checkout is intentionally not accepted.
    try:
        archived = (ROOT / ".cora-archive-revision").read_text().strip()
    except OSError:
        archived = ""
    if re.fullmatch(r"[a-fA-F0-9]{40}", archived):
        return archived.lower()
    # Source checkouts only: modified tracked files must never certify HEAD.
    if not (ROOT / ".git").exists():
        return ""
    try:
        if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                   cwd=ROOT, timeout=5, stderr=subprocess.DEVNULL).strip():
            return ""
        value = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                        text=True, timeout=5, stderr=subprocess.DEVNULL).strip()
        return value.lower() if re.fullmatch(r"[a-fA-F0-9]{40}", value) else ""
    except (OSError, subprocess.SubprocessError):
        return ""
