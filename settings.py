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
import paths

import providers
import vault
from safejson import read_json, write_json

SETTINGS_FILE = paths.user_data("settings.json")

# Shortcuts used to live in their own file; they're moved into settings.json.
OLD_SHORTCUTS_FILE = paths.user_data("shortcuts.json")

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
    # Which provider fills each role (see providers.py). Blank = not chosen yet.
    "roles": {role: "" for role in ("media_server", "movies", "tv")},
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
    "jellyfin": {
        "url": "",                # e.g. http://192.168.1.10:8096
        "api_key": "",            # made in Jellyfin: Dashboard > API Keys (Emby uses the same)
        "path_map": {},           # Jellyfin's library folder -> how this PC reaches it
        "rescan_after_move": True,
    },
}


# The secrets that go to the password store: (settings section, field).
# Derived from the registry so new available providers are covered automatically.
SECRETS = [(key, providers.secret_field(key))
           for key in providers.PROVIDERS if providers.is_available(key)]


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
    need_save = False
    if vault.available():
        for section, field in SECRETS:
            if section not in settings or field not in settings[section]:
                continue
            in_file = settings[section][field]
            settings[section][field] = vault.get(f"{section}.{field}") or in_file
            if in_file:  # from before the password store was used: move it over
                need_save = True
    if "roles" not in saved:
        _infer_roles(settings)   # one-time: pre-select whatever is already configured
        _backup_once()
        need_save = True
    if need_save:
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
    roles = data.get("roles", {})
    if not (isinstance(roles, dict)
            and all(isinstance(k, str) and isinstance(v, str) for k, v in roles.items())):
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
    jelly = data.get("jellyfin", {})
    if not (
        isinstance(jelly, dict)
        and all(isinstance(jelly.get(k, ""), str) for k in ("url", "api_key"))
        and isinstance(jelly.get("rescan_after_move", True), bool)
        and isinstance(jelly.get("path_map", {}), dict)
        and all(isinstance(k, str) and isinstance(v, str) for k, v in jelly.get("path_map", {}).items())
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


# ------------------------------------------------------- provider roles

def provider_configured(settings, key):
    """True when provider `key` has enough saved to use it."""
    config = settings.get(key, {})
    if not isinstance(config, dict):
        return False
    secret = providers.secret_field(key)
    if not (config.get("url") and config.get(secret)):
        return False
    # Library managers also need at least one mapped folder; a media server
    # maps libraries but can work from its own paths.
    if providers.role_of(key) in ("movies", "tv"):
        return any(config.get("path_map", {}).values())
    return True


def _infer_roles(settings):
    """Pre-select the provider already configured for each role (one-time)."""
    roles = settings.setdefault("roles", {r: "" for r in providers.ROLES})
    for role in providers.ROLES:
        if roles.get(role):
            continue
        for key in providers.available_for(role):
            if provider_configured(settings, key):
                roles[role] = key
                break


def _backup_once():
    """Copy settings.json aside once, before the first providers-era save."""
    backup = SETTINGS_FILE.with_name("settings.json.pre-providers")
    try:
        if SETTINGS_FILE.exists() and not backup.exists():
            backup.write_bytes(SETTINGS_FILE.read_bytes())
    except OSError:
        pass


def active_type(settings, role):
    """The provider chosen for `role`, or '' if none."""
    return settings.get("roles", {}).get(role, "")


def role_config(settings, role):
    """(type, config_block) for the active provider of `role`; ('', None) if unset."""
    chosen = active_type(settings, role)
    if not chosen:
        return "", None
    return chosen, settings.get(chosen)
