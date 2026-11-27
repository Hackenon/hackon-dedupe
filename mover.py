# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Piece 6: move unticked files to the _review folder, with undo.

Every batch of moves is logged in moves.json, so Undo can put each file back
exactly where it came from.
"""

import shutil
from datetime import datetime
from pathlib import Path
import paths

from safejson import read_json, write_json
from scan import REVIEW_FOLDER

MOVES_FILE = paths.user_data("moves.json")


def valid_moves(data):
    """A list of batches, each with a folder and a list of moves."""
    return isinstance(data, list) and all(
        isinstance(batch, dict) and isinstance(batch.get("folder"), str)
        and isinstance(batch.get("moves"), list)
        and all(isinstance(m, dict) and isinstance(m.get("path"), str)
                and isinstance(m.get("moved_to"), str) for m in batch["moves"])
        for batch in data
    )


def load_moves():
    return read_json(MOVES_FILE, default=list, valid=valid_moves)


def save_moves(moves):
    write_json(MOVES_FILE, moves)


def free_path(path):
    """Return `path`, or `name (2).jpg`, `name (3).jpg`... if it's taken.
    Moves never overwrite an existing file."""
    candidate, number = path, 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}")
        number += 1
    return candidate


PLEXIGNORE_LINE = f"{REVIEW_FOLDER}/*"


def hide_review_from_plex(folder):
    """Make sure Plex ignores the _review folder in `folder`.

    Plex reads a file named .plexignore in a library folder and skips anything
    it lists. Adds the line `_review/*`, creating the file if needed. An
    existing .plexignore is never changed beyond adding that one line.
    Returns a message for the page, or None if nothing needed doing.
    """
    path = Path(folder) / ".plexignore"
    try:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(line.strip() == PLEXIGNORE_LINE for line in text.splitlines()):
                return None  # already there
            ending = "" if text.endswith("\n") or not text else "\n"
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"{ending}# Added by HackOn Photo & Video DeDupe: keep the review folder out of Plex\n{PLEXIGNORE_LINE}\n")
            return f"ADDED {PLEXIGNORE_LINE} TO .plexignore SO PLEX SKIPS THE REVIEW FOLDER"
        path.write_text(
            f"# Added by HackOn Photo & Video DeDupe: keep the review folder out of Plex\n{PLEXIGNORE_LINE}\n",
            encoding="utf-8",
        )
        return "CREATED .plexignore SO PLEX SKIPS THE REVIEW FOLDER"
    except OSError as error:
        return f"COULDN'T UPDATE .plexignore ({error}). PLEX MAY SHOW THE REVIEW FOLDER."


def files_to_move(results):
    """Yield (group, file) for every unticked file that will be moved.

    A group with nothing ticked is skipped completely: we never move every
    copy of a photo.
    """
    for group in results["groups"]:
        if not any(file["keep"] and not file.get("moved_to") for file in group["files"]):
            continue
        for file in group["files"]:
            if not file["keep"] and not file.get("moved_to"):
                yield group, file


def move_extras(results, write_plexignore=False):
    """Move every unticked file into _review. Return (how many moved, Plex note or None).

    `write_plexignore` adds `_review/*` to .plexignore in the folder, but only
    when the caller confirms the folder is part of a Plex library.
    """
    folder = Path(results["folder"])
    plex_note = hide_review_from_plex(folder) if (write_plexignore and any(files_to_move(results))) else None
    batch = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "folder": str(folder),
        "moves": [],
    }

    for group, file in list(files_to_move(results)):
        source = folder / file["path"]
        if not source.exists():
            continue  # already gone; nothing to do
        target = free_path(folder / REVIEW_FOLDER / file["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(source, target)

        file["moved_to"] = str(target.relative_to(folder))
        batch["moves"].append(
            {"group": group["id"], "path": file["path"], "moved_to": file["moved_to"]}
        )

    if batch["moves"]:
        moves = load_moves()
        moves.append(batch)
        save_moves(moves)
    return len(batch["moves"]), plex_note


def undo_last(results):
    """Put back the most recent batch of moves. Return (restored, skipped)."""
    moves = load_moves()
    if not moves:
        return 0, 0
    batch = moves.pop()
    folder = Path(batch["folder"])

    # Look up each file's entry in results so we can clear its "moved" mark.
    same_folder = Path(results["folder"]) == folder
    entries = {
        (group["id"], file["path"]): file
        for group in results["groups"] for file in group["files"]
    } if same_folder else {}

    restored = skipped = 0
    for move in reversed(batch["moves"]):
        source = folder / move["moved_to"]
        target = folder / move["path"]
        if target.exists() or not source.exists():
            skipped += 1  # never overwrite; leave it in _review
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(source, target)
        entry = entries.get((move["group"], move["path"]))
        if entry:
            entry.pop("moved_to", None)
        restored += 1

    save_moves(moves)
    return restored, skipped
