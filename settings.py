"""App settings, saved to settings.json: the media apps from the setup
screen, and the folder shortcuts from the photo scan page.

Nothing personal (server addresses, API keys, folder paths) lives in the
code. settings.json is listed in .gitignore, so it never ends up in Git.

API keys and the Plex token are kept in the computer's password store when
it has one (see vault.py), and are only in settings.json when it doesn't.
"""

import copy
import uuid
from pathlib import Path

import vault
from safejson import read_json, write_json

SETTINGS_FILE = Path(__file__).parent / "settings.json"

# Shortcuts used to live in their own file; they're moved into settings.json.
OLD_SHORTCUTS_FILE = Path(__file__).parent / "shortcuts.json"

# The media apps the setup screen knows about: settings key -> details.
SERVICES = {
    "radarr": {"name": "Radarr", "media": "movies", "port": 7878},
    "sonarr": {"name": "Sonarr", "media": "TV shows", "port": 8989},
}

DEFAULTS = {
    "setup_done": False,          # True once you've saved or skipped the setup screen
    "shortcuts": [],              # photo folder shortcuts: [{"name": ..., "path": ...}]
    "media_details": "button",    # read missing video details: "button" (after a scan) or "auto"
    "bug_report_repo": "",        # GitHub repository for bug reports, e.g. "owner/hackon-dedupe"
    # One block per service, e.g. "radarr": {"url": ..., "api_key": ..., "path_map": {...}}
    **{
        service: {
            "url": "",            # e.g. http://192.168.1.10:7878
            "api_key": "",
            "path_map": {},       # the app's folder -> how this PC reaches it
            "move_to": "",        # default folder for moved extras (blank = _review in each root)
        }
        for service in SERVICES
    },
    "plex": {
        "url": "",                # e.g. http://192.168.1.10:32400
        "token": "",              # from PIN sign-in; never shown on any page
        "client_id": "",          # this app's ID with Plex, made once
        "path_map": {},           # Plex's library folder -> how this PC reaches it
        "rescan_after_move": True,
    },
}


# The secrets that go to the password store: (settings section, field).
SECRETS = [("radarr", "api_key"), ("sonarr", "api_key"), ("plex", "token")]


def is_configured(settings, service):
    """True when a service has an address, a key and at least one mapped folder."""
    config = settings.get(service, {})
    return bool(config.get("url") and config.get("api_key") and any(config.get("path_map", {}).values()))


def load_settings():
    """Return the saved settings, with defaults filled in for anything missing."""
    if OLD_SHORTCUTS_FILE.exists():
        move_old_shortcuts()
    settings = copy.deepcopy(DEFAULTS)
    saved = read_json(SETTINGS_FILE, default=dict, valid=valid_settings)
    for key, value in saved.items():
        if isinstance(value, dict) and isinstance(settings.get(key), dict):
            settings[key].update(value)
        else:
            settings[key] = value
    if vault.available():
        still_in_file = False
        for section, field in SECRETS:
            in_file = settings[section][field]
            settings[section][field] = vault.get(f"{section}.{field}") or in_file
            still_in_file = still_in_file or bool(in_file)
        if still_in_file:  # from before the password store was used: move them over
            save_settings(settings)
    return settings


def valid_shortcuts(data):
    """A list of {"name": ..., "path": ...} entries."""
    return isinstance(data, list) and all(
        isinstance(s, dict) and isinstance(s.get("name"), str) and isinstance(s.get("path"), str)
        for s in data
    )


def move_old_shortcuts():
    """One-time move: copy shortcuts.json into settings.json, then rename the
    old file to shortcuts.json.migrated (kept, not deleted)."""
    old = read_json(OLD_SHORTCUTS_FILE, default=list, valid=valid_shortcuts)
    saved = read_json(SETTINGS_FILE, default=dict, valid=valid_settings)
    known = {s["path"] for s in saved.get("shortcuts", [])}
    saved["shortcuts"] = saved.get("shortcuts", []) + [s for s in old if s["path"] not in known]
    write_json(SETTINGS_FILE, saved)
    if OLD_SHORTCUTS_FILE.exists():  # read_json may already have set a broken one aside
        target, number = OLD_SHORTCUTS_FILE.with_name("shortcuts.json.migrated"), 2
        while target.exists():  # Windows won't rename over an existing file
            target = OLD_SHORTCUTS_FILE.with_name(f"shortcuts.json.migrated-{number}")
            number += 1
        OLD_SHORTCUTS_FILE.rename(target)


def valid_settings(data):
    """settings.json must be a dictionary, and each service's part must look right."""
    if not isinstance(data, dict):
        return False
    if not valid_shortcuts(data.get("shortcuts", [])):
        return False
    if data.get("media_details", "button") not in ("button", "auto"):
        return False
    if not isinstance(data.get("bug_report_repo", ""), str):
        return False
    plex = data.get("plex", {})
    if not (
        isinstance(plex, dict)
        and all(isinstance(plex.get(k, ""), str) for k in ("url", "token", "client_id"))
        and isinstance(plex.get("rescan_after_move", True), bool)
        and isinstance(plex.get("path_map", {}), dict)
        and all(isinstance(k, str) and isinstance(v, str) for k, v in plex.get("path_map", {}).items())
    ):
        return False
    for service in SERVICES:
        config = data.get(service, {})
        if not (
            isinstance(config, dict)
            and isinstance(config.get("url", ""), str)
            and isinstance(config.get("api_key", ""), str)
            and isinstance(config.get("path_map", {}), dict)
            and all(isinstance(k, str) and isinstance(v, str) for k, v in config.get("path_map", {}).items())
        ):
            return False
    return True


def save_settings(settings):
    """Save settings.json. Secrets go to the password store instead, when there is one."""
    if vault.available():
        settings = copy.deepcopy(settings)
        for section, field in SECRETS:
            if isinstance(settings.get(section), dict) and field in settings[section]:
                vault.put(f"{section}.{field}", settings[section][field])
                settings[section][field] = ""
    write_json(SETTINGS_FILE, settings)


def mask(secret):
    """Show only the last 4 characters of a secret, e.g. '••••a1b2'."""
    if not secret:
        return ""
    return "•" * 8 + secret[-4:]


def plex_client_id():
    """This app's ID with Plex: made once, then saved and reused."""
    settings = load_settings()
    if not settings["plex"]["client_id"]:
        settings["plex"]["client_id"] = str(uuid.uuid4())
        save_settings(settings)
    return settings["plex"]["client_id"]
