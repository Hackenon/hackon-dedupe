"""Tests for deleted.py tombstones. FILES is redirected to temp paths so the
real deleted_*.json are never touched."""
import tempfile
import shutil
import unittest
from datetime import datetime
from pathlib import Path

import deleted


class TestDeleted(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self._orig = deleted.FILES
        deleted.FILES = {
            "photos": self.dir / "dp.json",
            "movies": self.dir / "dm.json",
            "tv": self.dir / "dt.json",
        }

    def tearDown(self):
        deleted.FILES = self._orig
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_load_empty_default(self):
        self.assertEqual(deleted.load("photos"), {"version": deleted.VERSION, "items": []})

    def test_record_appends_and_returns_count(self):
        n = deleted.record("photos", [{"original_path": "/a", "size": 10, "sha": "x"}])
        self.assertEqual(n, 1)
        items = deleted.load("photos")["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["sha"], "x")

    def test_record_empty_is_noop(self):
        self.assertEqual(deleted.record("photos", []), 0)
        self.assertFalse((self.dir / "dp.json").exists())

    def test_dedup_same_path_and_size_latest_wins(self):
        deleted.record("photos", [{"original_path": "/a", "size": 10, "v": "old"}])
        deleted.record("photos", [{"original_path": "/a", "size": 10, "v": "new"}])
        items = deleted.load("photos")["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["v"], "new")

    def test_key_distinguishes_size(self):
        deleted.record("photos", [{"original_path": "/a", "size": 10},
                                   {"original_path": "/a", "size": 20}])
        self.assertEqual(len(deleted.load("photos")["items"]), 2)

    def test_kinds_are_independent(self):
        deleted.record("movies", [{"original_path": "/m", "size": 1}])
        self.assertEqual(deleted.load("photos")["items"], [])
        self.assertEqual(len(deleted.load("movies")["items"]), 1)

    def test_now_iso_is_tz_aware(self):
        parsed = datetime.fromisoformat(deleted.now_iso())
        self.assertIsNotNone(parsed.tzinfo)


if __name__ == "__main__":
    unittest.main()
