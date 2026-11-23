"""Find TV duplicates using Sonarr. Read-only: nothing is moved.

Works like the movie scan, but a show has one file per episode, so
duplicates are grouped by episode (S01E02): the file Sonarr tracks for that
episode is the "real" one, and any other copy of the same episode is a
possible duplicate. Extra files whose episode can't be worked out from the
name are grouped under "?" for their show.
"""

import re
from datetime import datetime
from pathlib import Path
import paths

import arr
from mediatools import (file_entry, find_strays, folder_key, title_key,
                        unmapped_reason, valid_media_results, video_files)
from netpaths import translate
from safejson import read_json, write_json

TV_RESULTS_FILE = paths.user_data("tv_results.json")

TV_COUNTS = ("shows", "with_extra_files", "extra_files", "extra_bytes",
             "strays", "missing_folders", "unmapped")

# S01E02, s1e2, S01E02E03, S01E02-E03, S01.E02, and the older 1x02 style.
EPISODE = re.compile(
    r"[Ss](\d{1,2})[ ._-]?[Ee](\d{1,3})(?:[-_. ]?[Ee](\d{1,3}))?"
    r"|(?<!\d)(\d{1,2})x(\d{2,3})(?!\d)"
)


def episode_code(name):
    """Work out the episode from a file name: 'Show.S01E02.mkv' -> 'S01E02'.

    Two-episode files become 'S01E02-E03'. Returns None if there's no episode number.
    """
    match = EPISODE.search(name)
    if not match:
        return None
    if match.group(1):
        season, first, last = match.group(1), match.group(2), match.group(3)
    else:
        season, first, last = match.group(4), match.group(5), None
    code = f"S{int(season):02d}E{int(first):02d}"
    if last and int(last) != int(first):
        code += f"-E{int(last):02d}"
    return code


def run_tv_scan(settings, progress=print):
    """Compare Sonarr's shows with what's in their folders. Returns a dictionary."""
    config = settings["sonarr"]
    path_map = config["path_map"]

    progress("Asking Sonarr for its shows")
    shows = arr.series(config["url"], config["api_key"])
    progress(f"Sonarr knows {len(shows)} shows")

    groups, missing_folders, unmapped = [], [], []
    show_folders = set()
    shows_by_title = {}

    for number, show in enumerate(shows, start=1):
        if number % 25 == 0:
            progress(f"Checked {number} of {len(shows)} show folders")

        info = {"title": show.get("title", "?"), "year": show.get("year")}
        folder = translate(show.get("path", ""), path_map)
        shows_by_title.setdefault(title_key(info["title"]), []).append(
            {**info, "folder": str(folder) if folder else show.get("path", "")})

        if folder is None:
            unmapped.append({**info, "server_path": show.get("path", ""),
                             "reason": unmapped_reason(show.get("path", ""), path_map)})
            continue
        show_folders.add(folder_key(folder))
        if not folder.is_dir():
            if (show.get("statistics") or {}).get("episodeFileCount"):
                missing_folders.append({**info, "folder": str(folder)})
            continue

        files = video_files(folder)
        if not files:
            continue

        # Which of these files does Sonarr track? (One question per show.)
        tracked = {}
        for record in arr.episode_files(config["url"], config["api_key"], show["id"]):
            local = translate(record.get("path", ""), path_map)
            if local is not None:
                tracked[folder_key(local)] = record

        untracked = [f for f in files if folder_key(f) not in tracked]
        if not untracked:
            continue

        # Group every file by episode; keep only episodes with an untracked file.
        by_episode = {}
        for f in files:
            by_episode.setdefault(episode_code(f.name) or "?", []).append(f)

        for code in sorted(by_episode, key=lambda c: (c == "?", c)):
            episode_files = by_episode[code]
            if all(folder_key(f) in tracked for f in episode_files):
                continue
            entries = [
                file_entry(f, folder, tracked=True, app_file=tracked[folder_key(f)], app_name="Sonarr")
                for f in episode_files if folder_key(f) in tracked
            ]
            entries += [file_entry(f, folder) for f in sorted(episode_files) if folder_key(f) not in tracked]
            groups.append({
                **info,
                "episode": code,
                "folder": str(folder),
                "has_tracked": any(e["tracked"] for e in entries),
                "files": entries,
            })

    progress(f"{len(groups)} episodes have extra video files")

    progress("Looking for stray folders")
    strays = find_strays(path_map, show_folders, shows_by_title)
    progress(f"{len(strays)} stray folders or loose files")

    for number, group in enumerate(groups, start=1):
        group["id"] = number

    progress("TV scan complete")
    return {
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "counts": {
            "shows": len(shows),
            "with_extra_files": len(groups),
            "extra_files": sum(len(g["files"]) - sum(f["tracked"] for f in g["files"]) for g in groups),
            "extra_bytes": sum(f["size"] for g in groups for f in g["files"] if not f["tracked"]),
            "strays": len(strays),
            "missing_folders": len(missing_folders),
            "unmapped": len(unmapped),
        },
        "groups": groups,
        "strays": strays,
        "missing_folders": missing_folders,
        "unmapped": unmapped,
    }


def save_tv_results(results):
    write_json(TV_RESULTS_FILE, results)


def valid_tv_results(data):
    """Check tv_results.json has the shape the TV page relies on."""
    return valid_media_results(data, TV_COUNTS)


def load_tv_results():
    return read_json(TV_RESULTS_FILE, default=lambda: None, valid=valid_tv_results)
