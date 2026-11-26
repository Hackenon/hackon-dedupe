"""Tests for mover.py: free_path, files_to_move selection, .plexignore, and the
move->undo round-trip. MOVES_FILE is redirected to a temp path."""
import tempfile
import shutil
import unittest
from pathlib import Path

import mover


class TestFreePath(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_unused_path_unchanged(self):
        p = self.dir / "a.jpg"
        self.assertEqual(mover.free_path(p), p)

    def test_appends_number_when_taken(self):
        p = self.dir / "a.jpg"
        p.write_bytes(b"x")
        self.assertEqual(mover.free_path(p), self.dir / "a (2).jpg")
        (self.dir / "a (2).jpg").write_bytes(b"x")
        self.assertEqual(mover.free_path(p), self.dir / "a (3).jpg")


class TestFilesToMove(unittest.TestCase):
    def test_selects_unticked_but_keeps_one(self):
        results = {"groups": [
            {"id": 1, "files": [{"path": "a", "keep": True},
                                {"path": "b", "keep": False},
                                {"path": "c", "keep": False, "moved_to": "x"}]},
            {"id": 2, "files": [{"path": "d", "keep": False},   # nothing kept -> skip whole group
                                {"path": "e", "keep": False}]},
        ]}
        picked = [(g["id"], f["path"]) for g, f in mover.files_to_move(results)]
        self.assertEqual(picked, [(1, "b")])        # c already moved; group 2 skipped


class TestPlexIgnore(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_creates_then_idempotent(self):
        msg = mover.hide_review_from_plex(self.dir)
        self.assertIn("CREATED", msg)
        self.assertIn(mover.PLEXIGNORE_LINE, (self.dir / ".plexignore").read_text())
        self.assertIsNone(mover.hide_review_from_plex(self.dir))   # already there


class TestMoveUndo(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self._orig = mover.MOVES_FILE
        mover.MOVES_FILE = self.dir / "moves.json"

    def tearDown(self):
        mover.MOVES_FILE = self._orig
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_move_then_undo_round_trip(self):
        folder = self.dir / "lib"
        folder.mkdir()
        (folder / "keep.jpg").write_bytes(b"k")
        (folder / "dup.jpg").write_bytes(b"d")
        results = {"folder": str(folder), "groups": [
            {"id": 1, "files": [{"path": "keep.jpg", "keep": True},
                                {"path": "dup.jpg", "keep": False}]}]}
        moved, note = mover.move_extras(results)
        self.assertEqual(moved, 1)
        self.assertFalse((folder / "dup.jpg").exists())
        self.assertTrue(results["groups"][0]["files"][1].get("moved_to"))

        restored, skipped = mover.undo_last(results)
        self.assertEqual((restored, skipped), (1, 0))
        self.assertTrue((folder / "dup.jpg").exists())
        self.assertNotIn("moved_to", results["groups"][0]["files"][1])


if __name__ == "__main__":
    unittest.main()
