# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Tests for safejson.py: round-trip, default fallback, broken-file set-aside,
and atomic write."""
import tempfile
import shutil
import unittest
from pathlib import Path

import safejson


class TestSafeJson(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        safejson.notices.clear()

    def tearDown(self):
        safejson.notices.clear()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_round_trip(self):
        p = self.dir / "d.json"
        safejson.write_json(p, {"a": 1})
        self.assertEqual(safejson.read_json(p, default=dict), {"a": 1})

    def test_missing_returns_default(self):
        p = self.dir / "none.json"
        self.assertEqual(safejson.read_json(p, default=dict), {})
        self.assertEqual(safejson.read_json(p, default=list), [])

    def test_invalid_json_set_aside(self):
        p = self.dir / "d.json"
        p.write_text("{ not json", encoding="utf-8")
        self.assertEqual(safejson.read_json(p, default=dict), {})
        self.assertTrue(list(self.dir.glob("d.broken-*.json")))
        self.assertTrue(safejson.notices)

    def test_wrong_shape_set_aside(self):
        p = self.dir / "d.json"
        p.write_text('{"x": 1}', encoding="utf-8")
        result = safejson.read_json(p, default=list, valid=lambda d: isinstance(d, list))
        self.assertEqual(result, [])
        self.assertTrue(list(self.dir.glob("d.broken-*.json")))

    def test_valid_returns_data(self):
        p = self.dir / "d.json"
        p.write_text('{"a": 1}', encoding="utf-8")
        self.assertEqual(safejson.read_json(p, default=dict, valid=lambda d: "a" in d), {"a": 1})

    def test_atomic_leaves_no_tmp(self):
        p = self.dir / "d.json"
        safejson.write_json(p, {"a": 1})
        self.assertEqual([f.name for f in self.dir.glob("*.tmp")], [])

    def test_take_notices_clears(self):
        p = self.dir / "d.json"
        p.write_text("nope", encoding="utf-8")
        safejson.read_json(p, default=dict)
        self.assertTrue(safejson.take_notices())
        self.assertEqual(safejson.take_notices(), [])


if __name__ == "__main__":
    unittest.main()
