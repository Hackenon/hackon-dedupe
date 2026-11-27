# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Startup cleanup: remember files the user deleted out of _review.

After HackOn moves extra copies or stray folders into a `_review` folder, the
user may later delete them to reclaim space. The next time the app loads we
check whether those moved files are really gone and, if so, stop tracking them:

  * the undo history drops the vanished moves (an empty batch is removed), and
  * the scan results drop the vanished files. A duplicate group that falls to a
    single remaining file is removed too, since it is no longer a duplicate.

Rather than forgetting a vanished file outright, we first write everything we
know about it -- identity, size, original path, and (for photos) its perceptual
fingerprint and SHA-256 -- to a `deleted_*.json` tombstone (see deleted.py).
That record is the groundwork for the future "Advanced data recovery" feature
(docs/RECOVERY-DESIGN.md). The active scan results still drop the file, so the
review screens look exactly as before; the tombstone is purely additive.

Safety first: we only forget a file when we can *confirm* it is gone -- its
volume is reachable but the file is not there. A temporarily offline NAS looks
unreachable, so nothing is pruned until it comes back. We never delete anything
on disk here; we only forget records about files the user already deleted.
"""

from pathlib import Path

import deleted
import mediamover
import mover
from cache import FingerprintCache
from mediamover import root_folders, root_for
from moviescan import load_movie_results, save_movie_results
from results import load_results, save_results
from tvscan import load_tv_results, save_tv_results

# Movie/TV kind -> the singular label used in a tombstone's "category".
_LABEL = {"movies": "movie", "tv": "tv"}


def _summary():
    return {"moves": 0, "files": 0, "groups": 0, "strays": 0, "tombstoned": 0}


# ----- photos -------------------------------------------------------------

def clean_photo_reviews():
    """Prune vanished photo moves from results.json and moves.json."""
    done = _summary()
    _clean_photo_results(done)
    _clean_photo_moves(done)
    return done


def _photo_prints(cache_entries, abspath):
    """Perceptual fingerprint + SHA-256 for `abspath`, read from the cache.

    Returns (fingerprint_dict_or_None, sha256_or_None). We read the stored entry
    directly instead of FingerprintCache.get(), which would re-stat the now
    deleted file. The cache is keyed exactly as cache._key builds it.
    """
    fingerprint = sha256 = None
    look = cache_entries.get(f"look|{abspath}")
    if look and isinstance(look.get("value"), (list, tuple)) and look["value"]:
        value = look["value"]
        phash = int(value[0])
        fingerprint = {
            "phash": phash,
            "phash_hex": format(phash & ((1 << 64) - 1), "016x"),
            "pixels": value[1] if len(value) > 1 else None,
        }
    sha = cache_entries.get(f"sha|{abspath}")
    if sha and sha.get("value"):
        sha256 = sha["value"]
    return fingerprint, sha256


def _clean_photo_results(done):
    results = load_results()
    if not results:
        return
    folder = Path(results["folder"])
    if not folder.is_dir():
        return  # volume offline: don't touch anything
    cache_entries = FingerprintCache().entries
    tombstones = []
    changed = False
    for group in results["groups"]:
        kept = []
        for file in group["files"]:
            moved_to = file.get("moved_to")
            if moved_to is not None and not (folder / moved_to).exists():
                abspath = str((folder / file["path"]).absolute())
                fingerprint, sha256 = _photo_prints(cache_entries, abspath)
                tombstones.append({
                    "deleted_detected_at": deleted.now_iso(),
                    "category": "photo",
                    "original_path": abspath,
                    "moved_to": str((folder / moved_to).absolute()),
                    "size": file.get("size"),
                    "fingerprint": fingerprint,
                    "sha256": sha256,
                    "record": file,
                })
                done["files"] += 1
                changed = True
                continue  # confirmed deleted from _review
            kept.append(file)
        group["files"] = kept
    before = len(results["groups"])
    # A duplicate needs at least two files; a group that drops below that is
    # no longer a duplicate, so stop showing it.
    results["groups"] = [g for g in results["groups"] if len(g["files"]) >= 2]
    done["groups"] += before - len(results["groups"])
    done["tombstoned"] += deleted.record("photos", tombstones)
    if changed:
        save_results(results)


def _clean_photo_moves(done):
    moves = mover.load_moves()
    changed = False
    kept_batches = []
    for batch in moves:
        folder = Path(batch["folder"])
        if not folder.is_dir():
            kept_batches.append(batch)  # volume offline: keep the batch intact
            continue
        kept = [m for m in batch["moves"] if (folder / m["moved_to"]).exists()]
        if len(kept) != len(batch["moves"]):
            done["moves"] += len(batch["moves"]) - len(kept)
            changed = True
        if kept:
            batch["moves"] = kept
            kept_batches.append(batch)
    if changed:
        mover.save_moves(kept_batches)


# ----- movies and TV ------------------------------------------------------

_MEDIA = {
    "movies": ("radarr", load_movie_results, save_movie_results),
    "tv": ("sonarr", load_tv_results, save_tv_results),
}


def clean_media_reviews(kind, settings):
    """Prune vanished movie/TV moves from the results and undo logs."""
    done = _summary()
    service, load, save = _MEDIA[kind]
    roots = root_folders(settings, service)

    def confirmed_gone(abspath):
        """True only when the file's volume is reachable but the file is not."""
        path = Path(abspath)
        root = root_for(path, roots)
        if root is None or not root.is_dir():
            return False  # can't reach the volume: assume still there
        return not path.exists()

    _clean_media_results(kind, load, save, confirmed_gone, done)
    _clean_media_moves(kind, confirmed_gone, done)
    return done


def _media_extra_tombstone(kind, group, file):
    """Tombstone for a deleted extra copy inside a duplicate group."""
    folder = group.get("folder")
    name = file.get("name")
    original_path = str(Path(folder, name)) if folder and name else file.get("moved_to")
    return {
        "deleted_detected_at": deleted.now_iso(),
        "category": f"{_LABEL[kind]}-extra",
        "title": group.get("title"),
        "year": group.get("year"),
        "episode": group.get("episode"),
        "original_path": original_path,
        "moved_to": file.get("moved_to"),
        "size": file.get("size"),
        "fingerprint": None,   # movies/TV are matched by metadata, not perceptually hashed
        "sha256": None,
        "record": file,
    }


def _media_stray_tombstone(kind, stray):
    """Tombstone for a deleted stray file/folder."""
    suggestion = stray.get("suggestion") or {}
    return {
        "deleted_detected_at": deleted.now_iso(),
        "category": f"{_LABEL[kind]}-stray",
        "title": suggestion.get("title") or stray.get("name"),
        "year": suggestion.get("year"),
        "episode": None,
        "original_path": stray.get("path"),
        "moved_to": stray.get("moved_to"),
        "size": stray.get("size"),
        "fingerprint": None,
        "sha256": None,
        "record": stray,
    }


def _clean_media_results(kind, load, save, confirmed_gone, done):
    results = load()
    if not results:
        return
    tombstones = []
    changed = False
    for group in results.get("groups", []):
        kept = []
        for file in group["files"]:
            moved_to = file.get("moved_to")
            if moved_to is not None and confirmed_gone(moved_to):
                tombstones.append(_media_extra_tombstone(kind, group, file))
                done["files"] += 1
                changed = True
                continue
            kept.append(file)
        group["files"] = kept
    before = len(results.get("groups", []))
    results["groups"] = [g for g in results.get("groups", []) if len(g["files"]) >= 2]
    done["groups"] += before - len(results["groups"])

    kept_strays = []
    for stray in results.get("strays", []):
        moved_to = stray.get("moved_to")
        if moved_to is not None and confirmed_gone(moved_to):
            tombstones.append(_media_stray_tombstone(kind, stray))
            done["strays"] += 1
            changed = True
            continue
        kept_strays.append(stray)
    results["strays"] = kept_strays

    done["tombstoned"] += deleted.record(kind, tombstones)
    if changed:
        _recount_media(results)
        save(results)


def _recount_media(results):
    """Keep the summary counts in step after pruning (scan totals stay put)."""
    groups = results.get("groups", [])
    counts = results.setdefault("counts", {})
    counts["with_extra_files"] = len(groups)
    counts["extra_files"] = sum(
        len(g["files"]) - sum(bool(f.get("tracked")) for f in g["files"]) for g in groups
    )
    counts["extra_bytes"] = sum(
        f["size"] for g in groups for f in g["files"] if not f.get("tracked")
    )
    counts["strays"] = len(results.get("strays", []))


def _clean_media_moves(kind, confirmed_gone, done):
    moves = mediamover.load_moves(kind)
    changed = False
    kept_batches = []
    for batch in moves:
        kept = [m for m in batch["moves"] if not confirmed_gone(m["to"])]
        if len(kept) != len(batch["moves"]):
            done["moves"] += len(batch["moves"]) - len(kept)
            changed = True
        if kept:
            batch["moves"] = kept
            kept_batches.append(batch)
    if changed:
        mediamover.save_moves(kind, kept_batches)


# ----- run everything -----------------------------------------------------

def clean_all(settings):
    """Run every cleanup and return a combined summary."""
    total = _summary()
    for part in (clean_photo_reviews(),
                 clean_media_reviews("movies", settings),
                 clean_media_reviews("tv", settings)):
        for key in total:
            total[key] += part[key]
    return total
