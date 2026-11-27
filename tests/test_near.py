# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Tests for near.py: perceptual-hash distance, clustering, ranking, and the
copies-vs-similar split. The pure logic is tested with crafted integer
fingerprints; find_near_duplicates is tested with fingerprint_all mocked so no
real image decoding (PIL/imagehash) is needed."""
import tempfile
import shutil
import unittest
from unittest import mock
from pathlib import Path

import near


class TestDistance(unittest.TestCase):
    def test_zero_and_symmetry(self):
        self.assertEqual(near.distance(5, 5), 0)
        self.assertEqual(near.distance(0b1010, 0b0010), 1)
        self.assertEqual(near.distance(0b000, 0b111), 3)
        self.assertEqual(near.distance(0, 0xFFFFFFFFFFFFFFFF), 64)
        self.assertEqual(near.distance(12, 34), near.distance(34, 12))


def _photo(fp, pixels=0, path="/x"):
    return (Path(path), fp, pixels)


class TestGroupLookAlikes(unittest.TestCase):
    def test_identical_grouped_at_zero(self):
        groups = near.group_look_alikes([_photo(5, path="/a"), _photo(5, path="/b")], 0)
        self.assertEqual(len(groups), 1)
        self.assertEqual({p[0].name for p in groups[0]}, {"a", "b"})

    def test_threshold_is_inclusive(self):
        pair = [_photo(0b000, path="/a"), _photo(0b111, path="/b")]  # distance 3
        self.assertEqual(near.group_look_alikes(pair, 2), [])        # too strict
        self.assertEqual(len(near.group_look_alikes(pair, 3)), 1)    # exactly within

    def test_transitive_chaining(self):
        # a~b (2), b~c (2), but a~c is 4: union-find still merges all three.
        photos = [_photo(0b0000, path="/a"), _photo(0b0011, path="/b"), _photo(0b1111, path="/c")]
        groups = near.group_look_alikes(photos, 2)
        self.assertEqual(len(groups), 1)
        self.assertEqual({p[0].name for p in groups[0]}, {"a", "b", "c"})

    def test_isolated_photo_excluded(self):
        photos = [_photo(0, path="/a"), _photo(0, path="/b"), _photo(0xFF, path="/c")]
        groups = near.group_look_alikes(photos, 1)
        self.assertEqual(len(groups), 1)                             # only {a,b}; c alone
        self.assertEqual({p[0].name for p in groups[0]}, {"a", "b"})

    def test_two_separate_groups(self):
        photos = [_photo(0, path="/a"), _photo(0, path="/b"),
                  _photo(0xF0, path="/c"), _photo(0xF0, path="/d")]
        groups = near.group_look_alikes(photos, 0)
        self.assertEqual(len(groups), 2)


class TestBestFirst(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _file(self, name, nbytes):
        p = self.dir / name
        p.write_bytes(b"x" * nbytes)
        return p

    def test_higher_resolution_first(self):
        low = (self._file("low", 9999), 0, 100)      # big file, few pixels
        high = (self._file("high", 10), 0, 999)      # small file, many pixels
        self.assertEqual([p[0].name for p in near.best_first([low, high])], ["high", "low"])

    def test_pixel_tie_breaks_on_file_size(self):
        small = (self._file("small", 10), 0, 500)
        big = (self._file("big", 5000), 0, 500)      # same pixels, larger file
        self.assertEqual([p[0].name for p in near.best_first([small, big])], ["big", "small"])


class TestFindNearDuplicates(unittest.TestCase):
    def test_copies_vs_similar_split(self):
        # p1/p2 identical (distance 0 -> a copy); p3/p4 near but distinct (-> similar).
        photos = [
            (Path("/p1"), 0b0000, 10), (Path("/p2"), 0b0000, 10),   # identical
            (Path("/p3"), 0xFFFF, 10), (Path("/p4"), 0xFFF8, 10),  # distance 3, far from p1/p2
        ]
        with mock.patch.object(near, "fingerprint_all", return_value=photos):
            copies, similar = near.find_near_duplicates([None] * 4, progress=lambda *a: None)
        # Copies: the exact-fingerprint pair.
        copy_names = [{p[0].name for p in g} for g in copies]
        self.assertIn({"p1", "p2"}, copy_names)
        # Similar: the near-but-distinct pair; all-identical groups are filtered out.
        similar_names = [{p[0].name for p in g} for g in similar]
        self.assertIn({"p3", "p4"}, similar_names)
        self.assertNotIn({"p1", "p2"}, similar_names)


if __name__ == "__main__":
    unittest.main()
