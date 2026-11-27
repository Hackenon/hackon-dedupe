# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Tests for providers.py: the single-source-of-truth registry and its helpers."""
import unittest
import providers


class TestRegistry(unittest.TestCase):
    def test_is_available(self):
        for key in ("plex", "jellyfin", "radarr", "sonarr"):
            self.assertTrue(providers.is_available(key), key)
        for key in ("emby", "medusa", "sickgear", "nope"):
            self.assertFalse(providers.is_available(key), key)

    def test_role_of(self):
        self.assertEqual(providers.role_of("plex"), "media_server")
        self.assertEqual(providers.role_of("jellyfin"), "media_server")
        self.assertEqual(providers.role_of("radarr"), "movies")
        self.assertEqual(providers.role_of("sonarr"), "tv")
        self.assertIsNone(providers.role_of("nope"))

    def test_secret_field(self):
        self.assertEqual(providers.secret_field("plex"), "token")       # pin auth
        self.assertEqual(providers.secret_field("jellyfin"), "api_key")
        self.assertEqual(providers.secret_field("radarr"), "api_key")

    def test_for_role_order_and_filter(self):
        self.assertEqual(providers.for_role("media_server"), ["plex", "jellyfin", "emby"])
        self.assertEqual(providers.available_for("media_server"), ["plex", "jellyfin"])
        self.assertEqual(providers.planned_for("media_server"), ["emby"])
        self.assertEqual(providers.available_for("tv"), ["sonarr"])
        self.assertEqual(providers.planned_for("tv"), ["medusa", "sickgear"])

    def test_options_for_available_first(self):
        opts = providers.options_for("media_server")
        self.assertEqual([o["key"] for o in opts], ["plex", "jellyfin", "emby"])
        self.assertEqual([o["status"] for o in opts],
                         ["available", "available", "planned"])
        self.assertEqual(set(opts[0]), {"key", "name", "status", "port", "auth"})

    def test_discovery_targets_share_ports(self):
        targets = providers.discovery_targets()
        by_port = {t["port"]: t for t in targets}
        # Jellyfin + Emby share 8096 -> one combined, available (Jellyfin is available)
        self.assertEqual(by_port[8096]["keys"], ["jellyfin", "emby"])
        self.assertEqual(by_port[8096]["name"], "Jellyfin / Emby")
        self.assertEqual(by_port[8096]["kind"], "shared")
        self.assertEqual(by_port[8096]["status"], "available")
        # Medusa + SickGear share 8081 -> planned
        self.assertEqual(by_port[8081]["keys"], ["medusa", "sickgear"])
        self.assertEqual(by_port[8081]["status"], "planned")
        # Single-provider target keeps its own kind
        self.assertEqual(by_port[32400]["kind"], "plex")

    def test_discovery_targets_available_before_planned(self):
        statuses = [t["status"] for t in providers.discovery_targets()]
        self.assertNotIn("available", statuses[statuses.index("planned"):])


if __name__ == "__main__":
    unittest.main()
