"""Tests for settings.py role helpers and the one-time role migration.

All on crafted dicts; the live settings.json and the password vault are never
touched (these functions read only the dict and the provider registry)."""
import unittest
import settings


class TestProviderConfigured(unittest.TestCase):
    def test_media_server_needs_url_and_secret_only(self):
        self.assertTrue(settings.provider_configured({"plex": {"url": "u", "token": "t"}}, "plex"))
        self.assertFalse(settings.provider_configured({"plex": {"url": "u", "token": ""}}, "plex"))
        self.assertTrue(settings.provider_configured(
            {"jellyfin": {"url": "u", "api_key": "k"}}, "jellyfin"))

    def test_library_manager_also_needs_a_mapped_folder(self):
        self.assertFalse(settings.provider_configured(
            {"radarr": {"url": "u", "api_key": "k", "path_map": {}}}, "radarr"))
        self.assertTrue(settings.provider_configured(
            {"radarr": {"url": "u", "api_key": "k", "path_map": {"/a": "/b"}}}, "radarr"))
        self.assertFalse(settings.provider_configured(
            {"radarr": {"url": "u", "api_key": "", "path_map": {"/a": "/b"}}}, "radarr"))


class TestInferRoles(unittest.TestCase):
    def test_picks_configured_provider_per_role(self):
        s = {
            "roles": {"media_server": "", "movies": "", "tv": ""},
            "plex": {"url": "u", "token": "t"},
            "radarr": {"url": "u", "api_key": "k", "path_map": {"/a": "/b"}},
            "sonarr": {"url": "", "api_key": "", "path_map": {}},   # not configured
        }
        settings._infer_roles(s)
        self.assertEqual(s["roles"]["media_server"], "plex")
        self.assertEqual(s["roles"]["movies"], "radarr")
        self.assertEqual(s["roles"]["tv"], "")

    def test_does_not_override_existing_choice(self):
        s = {
            "roles": {"media_server": "jellyfin", "movies": "", "tv": ""},
            "plex": {"url": "u", "token": "t"},
        }
        settings._infer_roles(s)
        self.assertEqual(s["roles"]["media_server"], "jellyfin")


class TestRoleAccessors(unittest.TestCase):
    def test_active_type_and_role_config(self):
        s = {"roles": {"movies": "radarr"}, "radarr": {"url": "u"}}
        self.assertEqual(settings.active_type(s, "movies"), "radarr")
        self.assertEqual(settings.role_config(s, "movies"), ("radarr", {"url": "u"}))

    def test_unset_role_is_empty(self):
        self.assertEqual(settings.active_type({"roles": {}}, "tv"), "")
        self.assertEqual(settings.role_config({"roles": {}}, "tv"), ("", None))


if __name__ == "__main__":
    unittest.main()
