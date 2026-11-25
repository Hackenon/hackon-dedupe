"""Piece 8: find movie duplicates using Radarr. Read-only: nothing is moved.

For every movie Radarr knows, the file it tracks is the "real" one. Any
other video in the movie's folder is a possible duplicate. Folders in the
root folders that belong to no movie are listed separately as strays.
"""

from datetime import datetime
from pathlib import Path
import paths

import libmanager
from mediatools import (file_entry, find_strays, folder_key, same_path, title_key,
                        unmapped_reason, valid_media_results, video_files)
from netpaths import translate
from safejson import read_json, write_json

MOVIE_RESULTS_FILE = paths.user_data("movie_results.json")

MOVIE_COUNTS = ("movies", "with_extra_files", "extra_files", "extra_bytes",
                "strays", "missing_folders", "unmapped")


def run_movie_scan(settings, progress=print):
    """Compare Radarr's movies with what's in their folders. Returns a dictionary."""
    config = libmanager.config(settings, "movies")
    path_map = config["path_map"]

    progress("Asking Radarr for its movies")
    movies = libmanager.movies(settings)
    progress(f"Radarr knows {len(movies)} movies")

    groups, missing_folders, unmapped = [], [], []
    movie_folders = set()   # every movie folder, for spotting strays
    movies_by_title = {}

    for number, movie in enumerate(movies, start=1):
        if number % 100 == 0:
            progress(f"Checked {number} of {len(movies)} movie folders")

        info = {"title": movie.get("title", "?"), "year": movie.get("year")}
        folder = translate(movie.get("path", ""), path_map)
        movies_by_title.setdefault(title_key(info["title"]), []).append(
            {**info, "folder": str(folder) if folder else movie.get("path", "")})

        if folder is None:
            unmapped.append({**info, "server_path": movie.get("path", ""),
                             "reason": unmapped_reason(movie.get("path", ""), path_map)})
            continue
        movie_folders.add(folder_key(folder))
        if not folder.is_dir():
            if movie.get("hasFile"):
                missing_folders.append({**info, "server_path": movie.get("path", ""), "folder": str(folder)})
            continue

        radarr_file = movie.get("movieFile") if movie.get("hasFile") else None
        tracked_path = translate(radarr_file.get("path", ""), path_map) if radarr_file else None

        files = video_files(folder)
        untracked = [f for f in files if not (tracked_path and same_path(f, tracked_path))]
        if not untracked:
            continue  # only the tracked file (or nothing): no duplicates

        entries = [file_entry(f, folder, tracked=True, app_file=radarr_file, app_name="Radarr")
                   for f in files if tracked_path and same_path(f, tracked_path)]
        entries += [file_entry(f, folder) for f in sorted(untracked)]
        groups.append({
            **info,
            "folder": str(folder),
            "has_tracked": bool(radarr_file),
            "files": entries,
        })

    progress(f"{len(groups)} movies have extra video files")

    progress("Looking for stray folders")
    strays = find_strays(path_map, movie_folders, movies_by_title)
    progress(f"{len(strays)} stray folders or loose files")

    for number, group in enumerate(groups, start=1):
        group["id"] = number

    progress("Movie scan complete")
    return {
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "counts": {
            "movies": len(movies),
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


def save_movie_results(results):
    write_json(MOVIE_RESULTS_FILE, results)


def valid_movie_results(data):
    """Check movie_results.json has the shape the MOVIES page relies on."""
    return valid_media_results(data, MOVIE_COUNTS)


def load_movie_results():
    return read_json(MOVIE_RESULTS_FILE, default=lambda: None, valid=valid_movie_results)
