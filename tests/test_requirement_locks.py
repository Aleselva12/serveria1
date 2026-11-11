"""Keep the hand-written requirement lists and the hashed locks in step.

Nothing checked this before: PR #154 removed streamlit and rich from
requirements-core.txt and the deploy image kept installing them, because
requirements-deploy.lock was not regenerated. These checks read files only;
they never resolve or download anything.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGENERATE = (
    "Regenerate with the commands in deploy/README.md "
    "(section on requirements-deploy.lock and requirements-dev.lock)."
)


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def input_names(path):
    names = set()
    for raw in (ROOT / path).read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-r "):
            names |= input_names(line[3:].strip())
            continue
        names.add(normalize(re.split(r"[\[<>=!~;\s]", line, 1)[0]))
    return names


def lock_pins(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    return {normalize(n): v for n, v in re.findall(r"^([A-Za-z0-9_.\-]+)==([^\s;\\]+)", text, re.M)}


class RequirementLockTests(unittest.TestCase):
    def test_every_direct_dependency_is_locked(self):
        for inputs, lock in (("requirements-core.txt", "requirements-deploy.lock"),
                             ("requirements-test.txt", "requirements-dev.lock")):
            with self.subTest(lock=lock):
                missing = input_names(inputs) - set(lock_pins(lock))
                self.assertFalse(missing, f"{lock} lacks {sorted(missing)}. {REGENERATE}")

    def test_test_inputs_extend_core(self):
        # requirements-test.txt used to repeat the core list by hand, and the two drifted.
        self.assertLessEqual(input_names("requirements-core.txt"), input_names("requirements-test.txt"))

    def test_deploy_lock_has_no_leftovers_and_matches_ci_versions(self):
        # The dev lock is compiled from core plus test-only extras, so every package the
        # deploy image installs must also be in it, at the same version: CI then tests
        # exactly what production runs, and a package dropped from requirements-core.txt
        # but left in the deploy lock fails here.
        deploy, dev = lock_pins("requirements-deploy.lock"), lock_pins("requirements-dev.lock")
        leftovers = set(deploy) - set(dev)
        self.assertFalse(leftovers, f"requirements-deploy.lock still pins {sorted(leftovers)}. {REGENERATE}")
        drift = {n: (deploy[n], dev[n]) for n in deploy if deploy[n] != dev[n]}
        self.assertFalse(drift, f"deploy vs dev versions differ: {drift}. {REGENERATE}")

    def test_locks_carry_hashes(self):
        for lock in ("requirements-deploy.lock", "requirements-dev.lock"):
            with self.subTest(lock=lock):
                text = (ROOT / lock).read_text(encoding="utf-8")
                self.assertEqual(len(lock_pins(lock)), len(re.findall(r"^\S+==\S+.*\\\n\s+--hash=sha256:", text, re.M)))


if __name__ == "__main__":
    unittest.main()
