"""Source provenance for legacy updater archives, without using updater pointers."""
import io
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.infra import release_identity


class ArchiveRevisionTests(unittest.TestCase):
    def test_valid_archive_is_used_when_build_marker_is_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / ".cora-revision").write_text("")
            (root / ".cora-archive-revision").write_text("a" * 40)
            with patch.object(release_identity, "ROOT", root):
                self.assertEqual(release_identity.revision(), "a" * 40)

    def test_checkout_placeholder_cannot_certify_a_version(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / ".cora-revision").write_text("")
            (root / ".cora-archive-revision").write_text("$Format:%H$")
            with patch.object(release_identity, "ROOT", root):
                self.assertEqual(release_identity.revision(), "")

    def test_build_marker_remains_authoritative(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / ".cora-revision").write_text("b" * 40)
            (root / ".cora-archive-revision").write_text("a" * 40)
            with patch.object(release_identity, "ROOT", root):
                self.assertEqual(release_identity.revision(), "b" * 40)

    @unittest.skipUnless(shutil.which("git"), "git is required for archive integration")
    def test_git_archive_stamps_the_actual_commit(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in (".gitattributes", ".cora-archive-revision"):
                shutil.copyfile(source / name, root / name)
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL)
            git("init")
            git("add", ".gitattributes", ".cora-archive-revision")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false", "commit", "-m", "fixture")
            expected = git("rev-parse", "HEAD").decode().strip()
            with tarfile.open(fileobj=io.BytesIO(git("archive", "HEAD"))) as archive:
                stamped = archive.extractfile(".cora-archive-revision").read().decode().strip()
            self.assertEqual(stamped, expected)
