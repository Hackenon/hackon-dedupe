"""Tests for the API client parsers (pure logic only; no network)."""
import json
import unittest
from unittest import mock

import jellyfin
import arr
import netscan


class TestJellyfin(unittest.TestCase):
    def test_auth_header_is_modern_mediabrowser_token(self):
        h = jellyfin._auth_header("SECRET123")
        self.assertIn('Token="SECRET123"', h)
        self.assertIn("MediaBrowser", h)
        self.assertIn(jellyfin.PRODUCT, h)
        self.assertNotIn("X-Emby-Token", h)     # legacy header must not be used

    def test_normalize_url(self):
        self.assertEqual(jellyfin.normalize_url("192.168.1.10:8096"), "http://192.168.1.10:8096")
        self.assertEqual(jellyfin.normalize_url("http://host:8096/"), "http://host:8096")
        self.assertEqual(jellyfin.normalize_url("https://host"), "https://host")

    def test_parse_libraries_maps_and_filters(self):
        folders = [
            {"CollectionType": "movies", "Name": "Movies", "ItemId": "1",
             "Locations": ["/m", "", None]},
            {"CollectionType": "tvshows", "Name": "TV", "ItemId": "2", "Locations": ["/t"]},
            {"CollectionType": "homevideos", "Name": "Home", "Locations": ["/h"]},
            {"CollectionType": "music", "Name": "Music", "Locations": ["/mus"]},   # skipped
            {"CollectionType": None, "Name": "Weird"},                              # skipped
        ]
        libs = jellyfin._parse_libraries(folders)
        self.assertEqual([l["type"] for l in libs], ["Movies", "TV", "Photos"])
        self.assertEqual(libs[0]["key"], "1")
        self.assertEqual(libs[0]["folders"], ["/m"])          # blank/None dropped
        self.assertEqual(libs[2]["key"], "Home")              # falls back to Name

    def test_parse_libraries_empty(self):
        self.assertEqual(jellyfin._parse_libraries(None), [])
        self.assertEqual(jellyfin._parse_libraries([]), [])


class TestArr(unittest.TestCase):
    def test_normalize_url(self):
        self.assertEqual(arr.normalize_url("10.0.0.2:7878"), "http://10.0.0.2:7878")
        self.assertEqual(arr.normalize_url("http://x:7878/"), "http://x:7878")

    def test_status_requires_version(self):
        with mock.patch.object(arr, "call", return_value={"version": "5.2"}):
            self.assertEqual(arr.status("u", "k"), {"version": "5.2"})
        with mock.patch.object(arr, "call", return_value={}):
            with self.assertRaises(arr.ArrError):
                arr.status("u", "k")

    def test_root_folders_extracts_paths(self):
        with mock.patch.object(arr, "call", return_value=[{"path": "/a"}, {"path": "/b"}]):
            self.assertEqual(arr.root_folders("u", "k"), ["/a", "/b"])


class TestNetscanConfirmEmby(unittest.TestCase):
    def _confirm(self, payload):
        m = mock.MagicMock()
        m.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        with mock.patch("netscan.urllib.request.urlopen", m):
            return netscan._confirm_emby("http://host:8096")

    def test_jellyfin_by_product(self):
        self.assertEqual(self._confirm({"ProductName": "Jellyfin Server", "Id": "abc", "Version": "10.9"}),
                         ("jellyfin", "Jellyfin", "abc"))

    def test_emby_by_product(self):
        self.assertEqual(self._confirm({"ProductName": "Emby Server", "Id": "xyz"}),
                         ("emby", "Emby", "xyz"))

    def test_jellyfin_by_heuristic(self):
        self.assertEqual(self._confirm({"Version": "10.9", "ServerName": "Home", "Id": "h1"}),
                         ("jellyfin", "Jellyfin", "h1"))

    def test_unknown_is_none(self):
        self.assertIsNone(self._confirm({"ProductName": "Plex Media Server"}))


if __name__ == "__main__":
    unittest.main()
