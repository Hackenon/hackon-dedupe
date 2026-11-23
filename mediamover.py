"""Piece 9: move extra movie/TV copies and stray folders into _review, with undo.

Like the photo mover, but files live under Radarr/Sonarr *root folders*, not
one scanned folder. A moved file or folder goes to `_review` inside the root
folder it came from, keeping the path below that root. Each move batch is saved
(one file per kind) so Undo can put everything back exactly.
"""

import shutil
from datetime import datetime
from pathlib import Path
import paths

from mover import free_path, hide_review_from_plex
from safejson import read_json, write_json
from scan import REVIEW_FOLDER

# One undo log per kind, next to the results files.
MOVES_FILES = {
    "movies": paths.user_data("movie_moves.json"),
    "tv": paths.user_data("tv_moves.json"),
}


def valid_moves(data):
    return isinstance(data, list) and all(
        isinstance(b, dict) and isinstance(b.get("moves"), list)
        and all(isinstance(m, dict) and isinstance(m.get("from"), str)
                and isinstance(m.get("to"), str) for m in b["moves"])
        for b in data
    )


def load_moves(kind):
    return read_json(MOVES_FILES[kind], default=list, valid=valid_moves)


def save_moves(kind, moves):
    write_json(MOVES_FILES[kind], moves)


def root_folders(settings, service):
    """The mapped root folders for this service, as Paths (longest first, so the
    most specific root wins when one sits inside another)."""
    mapped = [local for local in settings[service]["path_map"].values() if local]
    return sorted((Path(p) for p in mapped), key=lambda p: len(str(p)), reverse=True)


def root_for(path, roots):
    """The root folder that contains `path`, or None."""
    target = str(path).replace("\\", "/").rstrip("/").lower()
    for root in roots:
        base = str(root).replace("\\", "/").rstrip("/").lower()
        if target == base or target.startswith(base + "/"):
            return root
    return None


def _review_target(source, root):
    """Where `source` goes inside `root`'s _review, keeping its path below root."""
    relative = Path(source).relative_to(root)
    return free_path(root / REVIEW_FOLDER / relative)


def things_to_move(results, roots):
    """Yield the moves the current ticks ask for, as dicts the page and the
    mover both understand. Nothing is touched here.

    - group files: any extra copy switched to MOVE (keep is False), as long as
      the group still keeps at least one file (never move every copy).
    - strays: any stray folder or loose file ticked to move.
    """
    for group in results.get("groups", []):
        files = group["files"]
        if not any(f["keep"] and not f.get("moved_to") for f in files):
            continue  # nothing kept: skip the whole group, like photos
        for index, file in enumerate(files):
            if file["keep"] or file.get("moved_to"):
                continue
            source = Path(group["folder"]) / file["name"]
            root = root_for(source, roots)
            if root is None:
                continue
            yield {"type": "file", "group": group["id"], "index": index,
                   "tracked": file.get("tracked", False),
                   "from": str(source), "root": str(root)}
    for stray in results.get("strays", []):
        if not stray.get("move") or stray.get("moved_to") or stray.get("kind") == "empty folder":
            continue
        source = Path(stray["path"])
        root = root_for(source, roots)
        if root is None:
            continue
        yield {"type": "stray", "path": stray["path"],
               "from": str(source), "root": str(root)}


def tracked_in(plan):
    """How many of the planned moves are files Radarr/Sonarr still tracks."""
    return sum(1 for move in plan if move.get("tracked"))


def apply_moves(results, settings, service, plan, destination=None):
    """Carry out `plan` (from things_to_move). Returns (count, notes).

    Marks moved things in `results` and records an undo batch.

    `destination` None moves each item into `_review` inside its own root folder
    (keeping the path below root) and hides `_review` from Plex — the default
    quarantine. A `destination` folder instead moves each item straight into that
    folder by name (used for a chosen default or a browsed relocation); nothing is
    hidden, since that location is meant to be seen.
    """
    notes = []
    touched_roots = set()
    dest_dir = Path(destination) if destination else None
    batch = {"time": datetime.now().isoformat(timespec="seconds"), "moves": []}

    for move in plan:
        source = Path(move["from"])
        if not source.exists():
            continue  # already gone
        root = Path(move["root"])
        if dest_dir is not None:
            target = free_path(dest_dir / source.name)
        else:
            target = _review_target(source, root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        if dest_dir is None:
            touched_roots.add(root)
        record = {"type": move["type"], "from": move["from"], "to": str(target)}
        if move["type"] == "file":
            file = results["groups"][_group_pos(results, move["group"])]["files"][move["index"]]
            file["moved_to"] = str(target)
            record.update(group=move["group"], index=move["index"])
        else:
            for stray in results["strays"]:
                if stray["path"] == move["path"]:
                    stray["moved_to"] = str(target)
            record["path"] = move["path"]
        batch["moves"].append(record)

    if batch["moves"]:
        moves = load_moves(_kind_for(service))
        moves.append(batch)
        save_moves(_kind_for(service), moves)
        for root in touched_roots:
            note = hide_review_from_plex(root)
            if note:
                notes.append(note)
    return len(batch["moves"]), notes


def undo_last(results, service):
    """Put the most recent batch back. Returns (restored, skipped)."""
    kind = _kind_for(service)
    moves = load_moves(kind)
    if not moves:
        return 0, 0
    batch = moves.pop()
    restored = skipped = 0
    for move in reversed(batch["moves"]):
        source = Path(move["to"])
        target = Path(move["from"])
        if target.exists() or not source.exists():
            skipped += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        _clear_moved_mark(results, move)
        restored += 1
    save_moves(kind, moves)
    return restored, skipped


def _group_pos(results, group_id):
    for pos, group in enumerate(results["groups"]):
        if group["id"] == group_id:
            return pos
    return None


def _clear_moved_mark(results, move):
    if move["type"] == "file":
        pos = _group_pos(results, move.get("group"))
        if pos is not None and move.get("index", -1) < len(results["groups"][pos]["files"]):
            results["groups"][pos]["files"][move["index"]].pop("moved_to", None)
    else:
        for stray in results.get("strays", []):
            if stray["path"] == move.get("path"):
                stray.pop("moved_to", None)


# movies <-> radarr, tv <-> sonarr
_SERVICE_KIND = {"radarr": "movies", "sonarr": "tv"}


def _kind_for(service):
    return _SERVICE_KIND[service]
