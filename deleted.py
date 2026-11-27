# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Tombstones for files the user deleted out of _review.

When startup cleanup confirms a file the user moved to `_review` is really gone
(see reviewcleanup.py), we no longer simply forget it. Everything we know about
it -- its identity, size, the path it used to live at, and (for photos) its
perceptual fingerprint and SHA-256 -- is written to a `deleted_*.json`
tombstone file instead of being discarded.

Keeping this record is the groundwork for the future "Advanced data recovery"
feature (see docs/RECOVERY-DESIGN.md): the fingerprint lets us pick a specific
deleted photo out of a pile of carved files, and the original path drives a
clean metadata-based recovery. Nothing here touches the user's disk beyond
these small JSON files.
"""

from datetime import datetime, timezone

import paths
from safejson import read_json, write_json

VERSION = 1

FILES = {
    "photos": paths.user_data("deleted_photos.json"),
    "movies": paths.user_data("deleted_movies.json"),
    "tv": paths.user_data("deleted_tv.json"),
}


def _valid(data):
    return isinstance(data, dict) and isinstance(data.get("items"), list)


def _empty():
    return {"version": VERSION, "items": []}


def load(kind):
    """Return the tombstone store for `kind` as {"version": int, "items": [...]}."""
    return read_json(FILES[kind], default=_empty, valid=_valid)


def now_iso():
    """A timezone-aware UTC timestamp, to the second, for when a loss was noticed."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _key(item):
    """Identity used so the same deleted file is never stored twice."""
    return f"{item.get('original_path')}|{item.get('size')}"


def record(kind, items):
    """Append tombstone `items`, replacing any earlier entry for the same file.

    `items` is a list of plain dicts built by the caller (reviewcleanup). Returns
    the number of records written. Safe to call with an empty list.
    """
    if not items:
        return 0
    store = load(kind)
    merged = {_key(it): it for it in store["items"]}
    for it in items:
        merged[_key(it)] = it
    store["items"] = list(merged.values())
    store["version"] = VERSION
    write_json(FILES[kind], store)
    return len(items)
