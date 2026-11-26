"""Tests for dirbrowse.py: the server-side directory listing for the folder browser."""
import os
import tempfile
import shutil
import unittest
from pathlib import Path

import dirbrowse


class TestListDirs(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_lists_only_subdirectories_sorted(self):
        (self.dir / "banana").mkdir()
        (self.dir / "Apple").mkdir()
        (self.dir / "cherry").mkdir()
        (self.dir / "file.txt").write_text("x")       # a file, must not appear
        result = dirbrowse.list_dirs(str(self.dir))
        self.assertEqual([e["name"] for e in result["entries"]], ["Apple", "banana", "cherry"])
        self.assertEqual(result["path"], str(self.dir.resolve()))
        self.assertEqual(result["parent"], str(self.dir.resolve().parent))

    def test_entry_paths_point_into_the_folder(self):
        (self.dir / "sub").mkdir()
        result = dirbrowse.list_dirs(str(self.dir))
        self.assertEqual(result["entries"][0]["path"], str((self.dir / "sub").resolve()))

    def test_nonexistent_returns_error_not_crash(self):
        result = dirbrowse.list_dirs(str(self.dir / "nope" / "missing"))
        self.assertEqual(result["entries"], [])
        self.assertIn("error", result)

    def test_no_path_lists_roots(self):
        result = dirbrowse.list_dirs(None)
        if os.name == "nt":
            self.assertTrue(result["drives"])             # drive list on Windows
            self.assertIsNone(result["parent"])
        else:
            self.assertEqual(result["drives"], [])        # POSIX: root
            self.assertEqual(result["path"], "/")
            self.assertIsNone(result["parent"])

    def test_drives_empty_off_windows(self):
        if os.name != "nt":
            self.assertEqual(dirbrowse._drives(), [])


if __name__ == "__main__":
    unittest.main()
