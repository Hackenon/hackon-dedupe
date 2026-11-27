# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Tests for mediamover.py path-mapping and move planning (pure logic)."""
import unittest
from pathlib import Path

import mediamover


class TestRootFolders(unittest.TestCase):
    def test_mapped_longest_first_blank_dropped(self):
        settings = {"radarr": {"path_map": {"a": "/media/movies",
                                            "b": "/media/movies/kids",
                                            "c": ""}}}
        self.assertEqual(mediamover.root_folders(settings, "radarr"),
                         [Path("/media/movies/kids"), Path("/media/movies")])


class TestRootFor(unittest.TestCase):
    def test_contained_path(self):
        self.assertEqual(mediamover.root_for("/media/movies/Film/f.mkv", [Path("/media/movies")]),
                         Path("/media/movies"))

    def test_case_insensitive(self):
        self.assertEqual(mediamover.root_for("/MEDIA/Movies/f", [Path("/media/movies")]),
                         Path("/media/movies"))

    def test_most_specific_root_wins(self):
        roots = [Path("/media/movies/kids"), Path("/media/movies")]   # longest first
        self.assertEqual(mediamover.root_for("/media/movies/kids/f.mkv", roots),
                         Path("/media/movies/kids"))

    def test_prefix_boundary_not_matched(self):
        # /media/movies2 must NOT match root /media/movies
        self.assertIsNone(mediamover.root_for("/media/movies2/f", [Path("/media/movies")]))

    def test_exact_match(self):
        self.assertEqual(mediamover.root_for("/media/movies", [Path("/media/movies")]),
                         Path("/media/movies"))

    def test_no_match(self):
        self.assertIsNone(mediamover.root_for("/other/f", [Path("/media/movies")]))


class TestThingsToMove(unittest.TestCase):
    def test_plans_files_and_strays(self):
        results = {
            "groups": [
                {"id": 1, "folder": "/media/movies/Film", "files": [
                    {"name": "keep.mkv", "keep": True},
                    {"name": "dup.mkv", "keep": False, "tracked": True},
                    {"name": "gone.mkv", "keep": False, "moved_to": "x"}]},
                {"id": 2, "folder": "/media/movies/Other", "files": [
                    {"name": "a.mkv", "keep": False},
                    {"name": "b.mkv", "keep": False}]},            # nothing kept -> skip
                {"id": 3, "folder": "/elsewhere/X", "files": [
                    {"name": "k.mkv", "keep": True},
                    {"name": "out.mkv", "keep": False}]},           # outside roots -> skip
            ],
            "strays": [
                {"path": "/media/movies/junk.nfo", "move": True, "kind": "file"},
                {"path": "/media/movies/empty", "move": True, "kind": "empty folder"},  # skip
                {"path": "/media/movies/unmarked", "move": False, "kind": "file"},        # skip
            ],
        }
        plan = list(mediamover.things_to_move(results, [Path("/media/movies")]))
        files = [m for m in plan if m["type"] == "file"]
        strays = [m for m in plan if m["type"] == "stray"]
        self.assertEqual(len(files), 1)
        self.assertEqual((files[0]["group"], files[0]["index"], files[0]["tracked"]), (1, 1, True))
        self.assertTrue(files[0]["from"].endswith("dup.mkv"))
        self.assertEqual(len(strays), 1)
        self.assertTrue(strays[0]["from"].endswith("junk.nfo"))

    def test_tracked_in_counts(self):
        self.assertEqual(mediamover.tracked_in([{"tracked": True}, {"tracked": False}, {}]), 1)


if __name__ == "__main__":
    unittest.main()
