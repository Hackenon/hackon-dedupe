# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Dispatch for the media-server role.

The media server rescans its library after a move and is told to ignore the
_review folder. Plex is implemented today; Jellyfin/Emby will add their branch
here and in a module of their own. Everything routes through whichever provider
fills the media_server role in settings.
"""

import plexbackdoor
import providers


class NotSupported(Exception):
    """The configured media server's support isn't built yet."""


def _resolve(settings):
    ptype = settings.get("roles", {}).get("media_server", "")
    config = settings.get(ptype) if ptype else None
    kind = providers.PROVIDERS.get(ptype, {}).get("kind")
    return ptype, kind, config


def provider_type(settings):
    return _resolve(settings)[0]


def config(settings):
    """The active media server's config block, or None."""
    return _resolve(settings)[2]


def signed_in(settings):
    """True when the active media server is reachable/authorised."""
    ptype, kind, cfg = _resolve(settings)
    if not (isinstance(cfg, dict) and cfg.get("url")):
        return False
    if kind == "plex":
        return bool(cfg.get("token") or plexbackdoor.is_open(settings))
    if kind in ("jellyfin", "emby"):
        return bool(cfg.get("api_key"))
    return False


def rescan_after_move(settings):
    """True when the active media server is set to rescan after a move and is usable."""
    cfg = config(settings)
    return bool(cfg and cfg.get("rescan_after_move", True) and signed_in(settings))


def libraries(settings, timeout=None):
    """List the active media server's libraries as [{key, title, type, folders}].
    Raises NotSupported if no media server (or an unimplemented one) is active."""
    ptype, kind, cfg = _resolve(settings)
    if not cfg:
        raise NotSupported("no media server is configured")
    if kind == "plex":
        import plex
        import settings as _settings
        kwargs = {} if timeout is None else {"timeout": timeout}
        return plex.libraries(cfg["url"], _settings.plex_client_id(), cfg["token"], **kwargs)
    if kind in ("jellyfin", "emby"):
        import jellyfin
        kwargs = {} if timeout is None else {"timeout": timeout}
        return jellyfin.libraries(cfg["url"], cfg.get("api_key", ""), **kwargs)
    raise NotSupported(f"{ptype} library listing isn't supported yet")


def ignore_review(settings, folder):
    """Make the active media server skip the _review folder inside `folder`.

    Plex reads a `.plexignore` in the library folder; Jellyfin/Emby skip any
    folder that contains a `.ignore` file, so we drop one inside `_review`.
    Returns a note for the page, or None when nothing applies.
    """
    from pathlib import Path
    ptype, kind, cfg = _resolve(settings)
    if kind == "plex":
        import mover
        return mover.hide_review_from_plex(folder)
    if kind in ("jellyfin", "emby"):
        review = Path(folder) / "_review"
        marker = review / ".ignore"
        try:
            if marker.exists():
                return None
            review.mkdir(parents=True, exist_ok=True)
            marker.write_text("", encoding="utf-8")
            return f"ADDED .ignore SO {ptype.upper()} SKIPS THE REVIEW FOLDER"
        except OSError as error:
            return f"COULDN'T ADD .ignore ({error}). {ptype.upper()} MAY SHOW THE REVIEW FOLDER."
    return None
