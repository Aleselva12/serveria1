"""Compare resolved versions from two release commits without contacting registries."""
import json
import re
import subprocess
from tempfile import TemporaryFile

NPM_LOCK = "frontend/package-lock.json"
PYTHON_LOCK = "requirements-deploy.lock"
VERSION = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?$")


def read_lock(engine, commit, path):
    with TemporaryFile() as output:
        result = subprocess.run(
            ["git", "--git-dir=" + str(engine.repo), "show", f"{commit}:{path}"],
            stdout=output, stderr=subprocess.DEVNULL, timeout=10, check=False,
        )
        if result.returncode or output.tell() > 4_000_000:
            raise ValueError("File di lock assente o non leggibile.")
        output.seek(0)
        return output.read(4_000_000).decode("utf-8")


def installed_versions(engine, commit):
    npm = json.loads(read_lock(engine, commit, NPM_LOCK))["packages"]
    versions = {
        ("npm", name): npm.get(f"node_modules/{name}", {}).get("version")
        for group in ("dependencies", "devDependencies")
        for name in npm[""].get(group, {})
    }
    python_lock = read_lock(engine, commit, PYTHON_LOCK)
    versions.update({("pip", re.sub(r"[-_.]+", "-", name.lower())): version
                     for name, version in re.findall(r"^([\w.-]+)==([^\s;\\]+)", python_lock, re.M)})
    return {key: value for key, value in versions.items() if isinstance(value, str)}


def change_type(before, after):
    if before == after:
        return "unchanged"
    if not before or not after:
        return "added" if after else "removed"
    old, new = VERSION.fullmatch(before), VERSION.fullmatch(after)
    if old and new:
        old, new = (tuple(int(part or 0) for part in version.groups()) for version in (old, new))
        if new > old:
            return next(kind for kind, a, b in zip(("major", "minor", "patch"), old, new, strict=True) if a != b)
        if new < old:
            return "downgrade"
    return "changed"


def compare(engine, installed, candidate):
    previous = installed_versions(engine, installed)
    following = installed_versions(engine, candidate) if candidate != installed else previous
    return [dict(ecosystem=ecosystem, name=name, installed=previous.get(key),
                 available=following.get(key), change=change_type(previous.get(key), following.get(key)))
            for key in sorted(previous.keys() | following.keys()) for ecosystem, name in [key]]
