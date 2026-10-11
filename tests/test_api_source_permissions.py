"""Reproduce private updater extraction and check image source access modes."""
import io
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ApiSourcePermissionTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', 'Requires POSIX source permission modes')
    def test_private_archive_source_grants_read_and_traversal_without_public_write(self):
        content = b'import unittest\nclass Fixture(unittest.TestCase):\n def test_one(self): self.assertEqual(1 + 1, 2)\n'
        archive_bytes = io.BytesIO()
        with tarfile.open(fileobj=archive_bytes, mode='w') as archive:
            folder = tarfile.TarInfo('tests'); folder.type = tarfile.DIRTYPE; folder.mode = 0o755
            archive.addfile(folder)
            file = tarfile.TarInfo('tests/test_fixture.py'); file.mode = 0o644; file.size = len(content)
            archive.addfile(file, io.BytesIO(content))
        with tempfile.TemporaryDirectory() as temporary:
            outer = Path(temporary); outer.chmod(0o755)
            app = outer/'app'; app.mkdir(mode=0o755)
            previous = os.umask(0o077)
            try:
                with tarfile.open(fileobj=io.BytesIO(archive_bytes.getvalue())) as archive:
                    archive.extractall(app, filter='data')
            finally: os.umask(previous)
            def discover():
                return subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(app/'tests'), '-v'],
                    cwd='/tmp', capture_output=True, text=True, timeout=15)
            self.assertEqual((app/'tests').stat().st_mode & 0o777, 0o700)
            owner = (app/'tests/test_fixture.py').stat().st_uid
            # Exercise the actual permission command shipped by the API Dockerfile.
            setup = next(line[4:] for line in (ROOT/'Dockerfile').read_text().splitlines()
                         if line.startswith('RUN ') and 'groupadd' in line)
            permission = shlex.split(setup.split('&&')[0].strip())
            self.assertEqual(permission[0], 'chmod', 'Normalize permissions before creating the API user')
            permission = [str(app) if value == '/app' else value for value in permission]
            subprocess.run(permission, check=True)
            result = discover()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Ran 1 test', result.stderr)
            self.assertEqual((app/'tests/test_fixture.py').stat().st_uid, owner)
            self.assertEqual((app/'tests').stat().st_mode & 0o777, 0o755)
            mode = (app/'tests/test_fixture.py').stat().st_mode
            self.assertTrue(mode & 0o004)
            self.assertEqual(mode & 0o022, 0)


if __name__ == '__main__': unittest.main()
