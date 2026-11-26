"""Tests for cache.py FingerprintCache: key format, hits, and invalidation."""
import json
import os
import tempfile
import shutil
import unittest
from pathlib import Path

from cache import FingerprintCache, VERSION


class TestFingerprintCache(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.cache_path = self.dir / "fp.json"

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, name, data):
        p = self.dir / name
        p.write_bytes(data)
        return p

    def test_put_then_get_hits(self):
        c = FingerprintCache(path=self.cache_path)
        f = self.write("a.bin", b"data")
        c.put("sha", f, "HASH")
        self.assertEqual(c.get("sha", f), "HASH")
        self.assertEqual(c.hits, 1)

    def test_missing_returns_none(self):
        c = FingerprintCache(path=self.cache_path)
        f = self.write("a.bin", b"data")
        self.assertIsNone(c.get("sha", f))

    def test_key_format(self):
        c = FingerprintCache(path=self.cache_path)
        f = self.write("a.bin", b"data")
        self.assertEqual(c._key("sha", f), f"sha|{Path(f).absolute()}")

    def test_invalidation_on_size_change(self):
        c = FingerprintCache(path=self.cache_path)
        f = self.write("a.bin", b"data")
        c.put("sha", f, "HASH")
        f.write_bytes(b"much-longer-data")       # size (and mtime) change
        self.assertIsNone(c.get("sha", f))

    def test_invalidation_on_mtime_change(self):
        c = FingerprintCache(path=self.cache_path)
        f = self.write("a.bin", b"data")
        os.utime(f, (1000, 1000))
        c.put("sha", f, "HASH")
        os.utime(f, (2000, 2000))                 # same size, new mtime
        self.assertIsNone(c.get("sha", f))

    def test_save_and_reload(self):
        f = self.write("a.bin", b"data")
        c = FingerprintCache(path=self.cache_path)
        c.put("sha", f, "HASH")
        c.save()
        c2 = FingerprintCache(path=self.cache_path)
        self.assertEqual(c2.get("sha", f), "HASH")

    def test_version_mismatch_ignored(self):
        f = self.write("a.bin", b"data")
        self.cache_path.write_text(json.dumps(
            {"version": VERSION + 99, "entries": {f"sha|{Path(f).absolute()}":
             {"size": 4, "modified": os.stat(f).st_mtime, "value": "STALE"}}}))
        c = FingerprintCache(path=self.cache_path)
        self.assertEqual(c.entries, {})


if __name__ == "__main__":
    unittest.main()
