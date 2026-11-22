"""Find photos that were moved or renamed after a scan ("trace" them).

When a file in the results is no longer where the scan saw it, the folder
that was scanned is swept for a file of the same size. A candidate counts
as the same file when one of these lines up:
  1. its modified time matches the one saved with its fingerprint
     (renaming or moving a file keeps its modified time), or
  2. its look fingerprint or SHA-256 fingerprint matches, or
  3. nothing was saved about the file, and it's the only one of that size
     with the same name.
Every lost file in the results is traced in the same sweep, so renaming
one folder is fixed in one go. Tracing changes nothing: recover() applies
what was found once you say so. The story lines are themed for the page.
"""

import os
from pathlib import Path

from exact import fingerprint
from near import UNREADABLE, look_fingerprint
from scan import PHOTO_TYPES, is_system_file, is_system_folder


def lost_files(results):
    """Yield (group, file) for every file that isn't where the scan saw it.
    Files already moved to _review are left alone."""
    folder = Path(results["folder"])
    for group in results["groups"]:
        for file in group["files"]:
            if not file.get("moved_to") and not (folder / file["path"]).exists():
                yield group, file


def sweep(folder, wanted_sizes):
    """Walk `folder`. Return ({size: [(path, modified time)]}, file count, folder count)
    for files whose size is in `wanted_sizes`. Sizes come with the folder listing,
    so no file is opened here."""
    by_size, files, folders = {}, 0, 0
    pending = [folder]
    while pending:
        current = pending.pop()
        folders += 1
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue  # unreadable folder: skip it
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    if not is_system_folder(entry.name):
                        pending.append(entry.path)
                elif entry.is_file() and not is_system_file(entry.name):
                    files += 1
                    stat = entry.stat()
                    if stat.st_size in wanted_sizes:
                        by_size.setdefault(stat.st_size, []).append((Path(entry.path), stat.st_mtime))
            except OSError:
                continue
    return by_size, files, folders


def saved_facts(cache, old_path):
    """What the fingerprint cache remembers about the file at its old path."""
    facts = {}
    if cache is None:
        return facts
    for kind in ("look", "sha"):
        entry = cache.entries.get(cache._key(kind, old_path))
        if entry:
            facts[kind] = entry["value"]
            facts["modified"] = entry["modified"]
    return facts


def same_file(old_path, candidate, modified, facts, only_one_with_name):
    """Return how the candidate was matched ("timestamp", "look", "sha", "name"), or None."""
    if facts.get("modified") == modified:
        return "timestamp"
    try:
        if "look" in facts and candidate.suffix.lower() in PHOTO_TYPES:
            if look_fingerprint(candidate)[0] == facts["look"][0]:
                return "look"
        if "sha" in facts and fingerprint(candidate) == facts["sha"]:
            return "sha"
    except UNREADABLE:
        return None
    if not facts and only_one_with_name and candidate.name.lower() == old_path.name.lower():
        return "name"
    return None


HOW = {
    "timestamp": "TIMESTAMP LOCK CONFIRMED",
    "look": "VISUAL SIGNATURE MATCH CONFIRMED",
    "sha": "SHA-256 SIGNATURE MATCH CONFIRMED",
    "name": "CALLSIGN MATCH CONFIRMED",
}


MATCHED_BY = {"timestamp": "TIMESTAMP", "look": "PICTURE", "sha": "SHA-256", "name": "NAME"}


def trace(results, target, cache=None, format_size=str):
    """Look for every lost file. `target` is the file entry that was asked for.

    Changes nothing. Returns a dict: found (bool), path (the target's new
    relative path), relocated (others found), still_lost, story (lines for
    the page), and matches: [(group id, file index, new path, saved facts)]
    to hand to recover(). For the summary on the page: found_files
    [{old, new, how, target}] and lost_names (files that couldn't be found).
    """
    folder = Path(results["folder"])
    name = Path(target["path"]).name
    story = [
        "*** INTRUSION DETECTED ***",
        "A HACKER HAS TAMPERED WITH THIS SYSTEM. TARGET FILE IS NOT WHERE WE LEFT IT.",
        f"TARGET: {name.upper()} // {format_size(target['size'])}"
        + (f" // {target['pixels']:,} PX" if target.get("pixels") else ""),
        f"LAST KNOWN POSITION: {str(Path(target['path']).parent).upper()}\\ ... NO CARRIER",
    ]
    answer = {"found": False, "path": None, "relocated": 0, "still_lost": 0,
              "story": story, "matches": [], "found_files": [], "lost_names": []}

    if not folder.is_dir():
        story += [f'SCAN VOLUME "{folder.name.upper()}" IS NOT RESPONDING.',
                  "THE HACKER TOOK THE WHOLE VOLUME. IT WAS RENAMED, MOVED OR DISCONNECTED.",
                  "RESCAN THE FOLDER WHERE IT LIVES NOW."]
        return answer

    lost = list(lost_files(results))
    if not any(file is target for _, file in lost):  # it's back where it was
        story.append("TARGET HAS RETURNED TO ITS POST. THE HACKER GOT COLD FEET.")
        answer.update(found=True, path=target["path"])
        return answer

    by_size, files, folders = sweep(folder, {file["size"] for _, file in lost})
    story.append(f'SWEEPING VOLUME "{folder.name.upper()}": {files:,} FILES IN {folders:,} SECTORS')

    in_results = {(folder / f["path"]).absolute() for g in results["groups"] for f in g["files"]}
    claimed = set()
    for group, file in lost:
        old_path = (folder / file["path"]).absolute()
        candidates = [(p, m) for p, m in by_size.get(file["size"], [])
                      if p.absolute() not in in_results and p not in claimed]
        if file is target:
            story.append(f"{len(candidates)} CANDIDATE(S) WITH IDENTICAL MASS ({format_size(file['size'])})")
        facts = saved_facts(cache, old_path)
        same_name = [p for p, _ in candidates if p.name.lower() == old_path.name.lower()]
        # Try files with the same name first: most moves keep the name.
        candidates.sort(key=lambda c: c[0].name.lower() != old_path.name.lower())
        for candidate, modified in candidates:
            how = same_file(old_path, candidate, modified, facts, len(same_name) == 1)
            if not how:
                continue
            claimed.add(candidate)
            new_path = str(candidate.relative_to(folder))
            answer["matches"].append((group["id"], group["files"].index(file), new_path, facts))
            answer["found_files"].append({"old": file["path"], "new": new_path,
                                          "how": MATCHED_BY[how], "target": file is target})
            if file is target:
                answer.update(found=True, path=new_path)
                story += [HOW[how], f"TARGET LOCATED: {new_path.upper()}"]
            else:
                answer["relocated"] += 1
            break
        else:
            answer["still_lost"] += 1
            answer["lost_names"].append(file["path"])

    if answer["relocated"]:
        story.append(f"{answer['relocated']} OTHER STOLEN FILE(S) LOCATED IN THE SAME SWEEP")
    if not answer["found"]:
        story += ["NO MATCHING SIGNATURE ON THIS VOLUME.",
                  f"TARGET HAS GONE DARK: DELETED, CHANGED, OR SMUGGLED OUT OF {folder.name.upper()}."]
    if answer["matches"]:
        story.append(f"AWAITING ORDERS: RECOVER {len(answer['matches'])} FILE(S)?")
    return answer


def recover(results, matches, cache=None):
    """Point the results at where the traced files are now. Matches whose
    file has gone again, or whose entry changed since the trace, are skipped.
    Returns how many were updated."""
    folder = Path(results["folder"])
    groups = {group["id"]: group for group in results["groups"]}
    updated = 0
    for group_id, index, new_path, facts in matches:
        group = groups.get(group_id)
        if not group or index >= len(group["files"]):
            continue
        file = group["files"][index]
        if file.get("moved_to") or (folder / file["path"]).exists() or not (folder / new_path).exists():
            continue
        file["path"] = new_path
        if cache is not None:  # so the next scan doesn't re-read these files
            for kind in ("look", "sha"):
                if kind in facts:
                    cache.put(kind, folder / new_path, facts[kind])
        updated += 1
    return updated
