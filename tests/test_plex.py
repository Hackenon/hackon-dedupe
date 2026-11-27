# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Tests for plex.py parsers (network stubbed via _request)."""
import unittest
from unittest import mock

import plex


class TestPlex(unittest.TestCase):
    def test_normalize_url(self):
        self.assertEqual(plex.normalize_url("10.0.0.2:32400"), "http://10.0.0.2:32400")
        self.assertEqual(plex.normalize_url("http://x:32400/"), "http://x:32400")

    def test_libraries_maps_and_filters(self):
        container = {"MediaContainer": {"Directory": [
            {"type": "movie", "key": 1, "title": "Movies", "Location": [{"path": "/m"}]},
            {"type": "show", "key": 2, "title": "TV", "Location": [{"path": "/t"}, {"path": ""}]},
            {"type": "photo", "key": 3, "title": "Pics", "Location": [{"path": "/p"}]},
            {"type": "artist", "key": 4, "title": "Music", "Location": [{"path": "/mus"}]},  # skip
        ]}}
        with mock.patch.object(plex, "_request", return_value=container):
            libs = plex.libraries("u", "cid", "tok")
        self.assertEqual([l["type"] for l in libs], ["Movies", "TV", "Photos"])
        self.assertEqual(libs[0]["key"], "1")
        self.assertEqual(libs[1]["folders"], ["/t"])      # blank path filtered

    def test_server_info_requires_version(self):
        ok = {"MediaContainer": {"version": "1.40", "friendlyName": "Home"}}
        with mock.patch.object(plex, "_request", return_value=ok):
            self.assertEqual(plex.server_info("u", "cid", "tok"), ("Home", "1.40"))
        with mock.patch.object(plex, "_request", return_value={"MediaContainer": {}}):
            with self.assertRaises(plex.PlexError):
                plex.server_info("u", "cid", "tok")

    def test_check_pin(self):
        with mock.patch.object(plex, "_request", return_value={"authToken": "TOK"}):
            self.assertEqual(plex.check_pin("cid", 5), "TOK")
        with mock.patch.object(plex, "_request", return_value={}):
            self.assertIsNone(plex.check_pin("cid", 5))


if __name__ == "__main__":
    unittest.main()
