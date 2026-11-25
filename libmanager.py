"""Dispatch for the library-manager role (movies / TV).

The library manager is the app that says authoritatively which file on disk is
the real copy to keep. Radarr (movies) and Sonarr (TV) share one API dialect
("arr"); future managers such as Medusa/SickGear will add their own branch here.
Everything routes through whichever provider fills the role in settings, so the
scans never name a specific app.
"""

import arr
import providers


class NotSupported(Exception):
    """The configured provider's library-manager support isn't built yet."""


def _resolve(settings, role):
    ptype = settings.get("roles", {}).get(role, "")
    config = settings.get(ptype) if ptype else None
    kind = providers.PROVIDERS.get(ptype, {}).get("kind")
    return ptype, kind, config


def provider_type(settings, role):
    return _resolve(settings, role)[0]


def display_name(settings, role):
    ptype = provider_type(settings, role)
    return providers.PROVIDERS.get(ptype, {}).get("name", ptype or "library manager")


def config(settings, role):
    """The active provider's config block for the role, or None."""
    return _resolve(settings, role)[2]


def configured(settings, role):
    """True when the role has a provider with an address, key and a mapped folder."""
    ptype, kind, cfg = _resolve(settings, role)
    if not (ptype and isinstance(cfg, dict)):
        return False
    return bool(cfg.get("url") and cfg.get("api_key")
                and any(cfg.get("path_map", {}).values()))


def movies(settings):
    ptype, kind, cfg = _resolve(settings, "movies")
    if kind == "arr":
        return arr.movies(cfg["url"], cfg["api_key"])
    raise NotSupported(f"{ptype or 'no movie manager'} isn't supported yet")


def series(settings):
    ptype, kind, cfg = _resolve(settings, "tv")
    if kind == "arr":
        return arr.series(cfg["url"], cfg["api_key"])
    raise NotSupported(f"{ptype or 'no TV manager'} isn't supported yet")


def episode_files(settings, series_id):
    ptype, kind, cfg = _resolve(settings, "tv")
    if kind == "arr":
        return arr.episode_files(cfg["url"], cfg["api_key"], series_id)
    raise NotSupported(f"{ptype or 'no TV manager'} isn't supported yet")


def rescan(settings, role):
    """Ask the role's manager to rescan its folders. Returns a page note, or None
    when the role isn't configured."""
    ptype, kind, cfg = _resolve(settings, role)
    if not (ptype and isinstance(cfg, dict) and cfg.get("url") and cfg.get("api_key")):
        return None
    name = providers.PROVIDERS[ptype]["name"]
    if kind == "arr":
        arr.rescan(cfg["url"], cfg["api_key"], name)
        return f"{name.upper()} IS RESCANNING ITS FOLDERS"
    raise NotSupported(f"{ptype} rescans aren't supported yet")
