import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import library_monitor as monitor
from search_agent import search_tools


class LibraryMonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'knowledge'
        self.root.mkdir()
        self.originals = Path(self.tmp.name) / 'originals'
        self.originals.mkdir()
        for obj, key, value in [
            (monitor, 'knowledge_root', lambda: self.root),
            (monitor, 'originals_root', lambda: self.originals),
            (monitor, '_safe_path', self.safe_path),
        ]:
            handle = patch.object(obj, key, value)
            handle.start()
            self.addCleanup(handle.stop)
        monitor._STOP.clear()

    def safe_path(self, value):
        path = Path(value)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Invalid path')
        target = self.root / path
        if target.is_symlink() or not target.resolve().is_relative_to(self.root.resolve()):
            raise ValueError('Invalid path')
        return target

    def test_default_is_opt_in_and_persisted(self):
        self.assertEqual(monitor.status()['folders'], [])
        (self.root/'work').mkdir()
        monitor.set_folder('work', True)
        self.assertEqual(monitor.status()['folders'], ['work'])
        self.assertIn('work', json.loads(monitor._state_path().read_text())['folders'])
        monitor.set_folder('work', False)
        self.assertEqual(monitor.status()['folders'], [])

    def test_root_escape_and_missing_paths_rejected(self):
        with self.assertRaises(ValueError):
            monitor.set_folder('../other', True)
        with self.assertRaises(ValueError):
            monitor.set_folder('.', True)
        with self.assertRaises(ValueError):
            monitor.set_folder('missing', True)

    def test_changes_are_recorded_only_after_first_scan(self):
        folder = self.root/'work'
        folder.mkdir()
        (folder/'one.txt').write_text('initial')
        monitor.set_folder('work', True)
        self.assertTrue(monitor.scan_once())
        self.assertEqual(monitor.status()['events'], [])
        (folder/'one.txt').write_text('new value')
        (folder/'two.txt').write_text('second')
        self.assertTrue(monitor.scan_once())
        events = monitor.status()['events']
        self.assertEqual({e['type'] for e in events}, {'added','changed'})
        self.assertEqual(monitor.status()['indexed_files'], 2)

    def test_failed_scan_does_not_replace_previous_snapshot(self):
        folder = self.root/'work'; folder.mkdir()
        (folder/'one.txt').write_text('original')
        monitor.set_folder('work', True)
        monitor.scan_once()
        with patch.object(monitor, 'MAX_FILES', 0):
            self.assertFalse(monitor.scan_once())
        self.assertEqual(monitor.status()['indexed_files'],1)


if __name__ == '__main__':
    unittest.main()
