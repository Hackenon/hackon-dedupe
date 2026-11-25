"""Scan a folder of movies or TV shows for duplicates, without Radarr or Sonarr.

Three kinds of duplicate are found and merged into one group per title:
  - same name:   the same movie (title + year) or episode (show + S01E02) in
                 more than one file, in any folders
  - identical:   byte-for-byte the same file, whatever it's called
  - same folder: (movies only) more than one video in one movie folder
Nothing is pre-ticked as KEEP: without Radarr/Sonarr there's no "real" copy,
so you pick. Read-only: nothing is moved.
"""

import re
from datetime import datetime
from pathlib import Path

from exact import find_exact_duplicates, SAMPLE_THRESHOLD
from mediatools import details_from_name, parse_folder_name, title_key, video_files
from tvscan import EPISODE, episode_code

REASON_LABELS = {"name": "same name", "identical": "identical files", "folder": "same movie folder"}


def movie_identity(path, root):
    """(key, display title) for a movie file: from its folder, or its own name if it's loose."""
    source = path.parent.name if path.parent != root else path.stem
    title, year = parse_folder_name(source)
    if not title:
        return None, None
    return (title, year), source


def show_identity(path, root):
    """(key, display title) for an episode: its show (top folder) plus episode code."""
    match = EPISODE.search(path.name)
    if not match:
        return None, None
    code = episode_code(path.name)
    relative = path.relative_to(root)
    show = relative.parts[0] if len(relative.parts) > 1 else path.name[:match.start()]
    show_title, _ = parse_folder_name(show.strip(" ._-"))
    if not show_title:
        return None, None
    return (show_title, code), f"{show.strip(' ._-')} :: {code}"


# Multi-part movies ("Movie cd1.avi" + "Movie cd2.avi", "part1"/"part2") are
# one copy of a movie, not duplicates of each other.
PART = re.compile(r"[ ._\-\[(](?:cd|dvd|dis[ck]|part|pt)[ ._\-]?(\d{1,2})(?=[ ._\-\])]|$)", re.I)


def stack_key(path):
    """Files of one multi-part movie share a stack key; other files get their own."""
    match = PART.search(path.stem)
    if not match:
        return (str(path).lower(),)
    return (str(path.parent).lower(), (path.stem[:match.start()] + path.stem[match.end():]).lower())


def name_details(path, root):
    """Quality details from the file name, falling back to its folder's name."""
    text = path.name if path.parent == root else f"{path.parent.name} {path.name}"
    return details_from_name(text)


def run_folder_scan(folder, kind, progress=print, cache=None):
    """Scan `folder` (movies or tv) for duplicates. Returns a results dictionary."""
    root = Path(folder)
    progress(f"Scanning {root}")
    videos = sorted(video_files(root))
    progress(f"Found {len(videos)} video files (extras and samples ignored)")

    # Units: each file on its own, except multi-part movies, which form one unit.
    units, unit_of, stacks = [], {}, {}
    for i, path in enumerate(videos):
        key = stack_key(path) if kind == "movies" else (str(path).lower(),)
        if key not in stacks:
            stacks[key] = len(units)
            units.append([])
        units[stacks[key]].append(i)
        unit_of[i] = stacks[key]

    # Link units that belong together. leader[u] points toward its group's first unit.
    leader = list(range(len(units)))
    links = []  # (unit, unit, reason)

    def find(u):
        while leader[u] != u:
            u = leader[u]
        return u

    def link_all(unit_list, reason):
        unit_list = list(dict.fromkeys(unit_list))  # unique, in order
        for other in unit_list[1:]:
            links.append((unit_list[0], other, reason))

    # 1. Same name: same movie (title + year) or same show + episode.
    identity = movie_identity if kind == "movies" else show_identity
    by_name = {}
    for i, path in enumerate(videos):
        key, _ = identity(path, root)
        if key:
            by_name.setdefault(key, []).append(unit_of[i])
    for unit_list in by_name.values():
        link_all(unit_list, "name")

    # 2. Identical contents. Big files are sampled (head + tail) for speed, so a
    #    match is "likely identical" until a full VERIFY confirms it.
    progress("Checking for identical files")
    position = {path: i for i, path in enumerate(videos)}
    sampled_links = []  # unit-sets whose identical match relied on sampling a big file
    for group in find_exact_duplicates(videos, cache, progress, sample=True):
        unit_list = [unit_of[position[p]] for p in group]
        link_all(unit_list, "identical")
        if any(p.stat().st_size > SAMPLE_THRESHOLD for p in group):
            sampled_links.append(unit_list)

    # 3. Several videos (several movies' worth) in one movie folder.
    if kind == "movies":
        by_folder = {}
        for i, path in enumerate(videos):
            if path.parent != root:
                by_folder.setdefault(path.parent, []).append(unit_of[i])
        for unit_list in by_folder.values():
            link_all(unit_list, "folder")

    for a, b, _ in links:
        leader[find(b)] = find(a)
    sampled_heads = {find(unit_list[0]) for unit_list in sampled_links}
    reasons = {}
    for a, b, reason in links:
        reasons.setdefault(find(a), set()).add(reason)

    members = {}
    for u in range(len(units)):
        members.setdefault(find(u), []).append(u)

    groups = []
    for head, unit_list in members.items():
        if len(unit_list) < 2:
            continue
        indexes = [i for u in unit_list for i in units[u]]
        first = videos[indexes[0]]
        _, display = identity(first, root)
        files = []
        for i in indexes:
            path = videos[i]
            files.append({
                "name": str(path.relative_to(root)),
                "size": path.stat().st_size,
                "tracked": False,
                "keep": False,  # you pick
                **name_details(path, root),
                "length": "",
                "details_from": "file name",
            })
        files.sort(key=lambda f: f["name"].lower())
        groups.append({
            "title": display or first.stem,
            "year": None,
            "folder": str(root),
            "has_tracked": False,
            "reasons": sorted(REASON_LABELS[r] for r in reasons.get(head, set())),
            "verify_sampled": head in sampled_heads,  # matched by sampling a big file; not yet full-hashed
            "verified": False,
            "files": files,
        })
    groups.sort(key=lambda g: g["title"].lower())
    for number, group in enumerate(groups, start=1):
        group["id"] = number
    progress(f"{len(groups)} groups of possible duplicates")
    progress("Folder scan complete")

    count_key = "movies" if kind == "movies" else "shows"
    return {
        "mode": "folder",
        "folder": str(root),
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "counts": {
            count_key: len(videos),
            "with_extra_files": len(groups),
            "extra_files": sum(len(g["files"]) - 1 for g in groups),
            # possible saving: everything except the largest file in each group
            "extra_bytes": sum(sum(f["size"] for f in g["files"]) - max(f["size"] for f in g["files"]) for g in groups),
            "strays": 0,
            "missing_folders": 0,
            "unmapped": 0,
        },
        "groups": groups,
        "strays": [],
        "missing_folders": [],
        "unmapped": [],
    }
