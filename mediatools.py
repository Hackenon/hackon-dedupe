# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Shared helpers for the Movies (Radarr) and TV (Sonarr) scans.

Finding video files, ignoring extras, reading quality details from names,
suggesting matches for stray folders, and listing stray folders.
"""

import os
import re
from pathlib import Path

from scan import is_system_file, is_system_folder

VIDEO_TYPES = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".ts", ".wmv", ".mpg", ".webm"}

# Extras that Plex, Radarr and Sonarr expect inside media folders. Ignored completely.
EXTRAS_FOLDERS = {
    "extras", "featurettes", "behind the scenes", "deleted scenes", "interviews",
    "scenes", "shorts", "trailers", "other", "samples", "sample",
}
EXTRAS_ENDINGS = (
    "-trailer", "-sample", "-featurette", "-behindthescenes", "-deleted",
    "-interview", "-scene", "-short", "-other", ".sample",
)


# ------------------------------------------------------------ small helpers

def is_extra(path):
    """True for trailers, samples and other extras, by folder or file name."""
    stem = path.stem.lower()
    return stem == "sample" or stem.endswith(EXTRAS_ENDINGS)


def video_files(folder):
    """Every video file under `folder`, skipping extras and system files."""
    found = []
    for current, subfolders, files in os.walk(folder):
        subfolders[:] = [name for name in subfolders
                         if not is_system_folder(name) and name.lower() not in EXTRAS_FOLDERS]
        for name in files:
            path = Path(current) / name
            if (path.suffix.lower() in VIDEO_TYPES and not is_system_file(name)
                    and not is_extra(path)):
                found.append(path)
    return found


def same_path(a, b):
    """Compare paths the way Windows does: ignoring case and slash direction."""
    normalize = lambda p: str(p).replace("\\", "/").rstrip("/").lower()
    return normalize(a) == normalize(b)


def details_from_name(name):
    """Guess quality details from a file or folder name, e.g. '1080p', 'x265'."""
    lower = name.lower()
    resolution = next((label for pattern, label in (
        (r"2160p|\b4k\b|uhd", "2160p"), (r"1080p", "1080p"), (r"720p", "720p"),
        (r"576p", "576p"), (r"480p|\bsd\b|dvdrip", "480p")) if re.search(pattern, lower)), "")
    codec = next((label for pattern, label in (
        (r"x265|h\.?265|hevc", "x265"), (r"x264|h\.?264|\bavc\b", "x264"),
        (r"\bav1\b", "AV1"), (r"xvid|divx", "XviD")) if re.search(pattern, lower)), "")
    source = next((label for pattern, label in (
        (r"remux", "Remux"), (r"blu-?ray|bdrip|brrip", "Bluray"), (r"web-?dl", "WEB-DL"),
        (r"webrip", "WEBRip"), (r"hdtv", "HDTV"), (r"dvd", "DVD")) if re.search(pattern, lower)), "")
    return {"resolution": resolution, "codec": codec, "source": source}


def title_key(text):
    """Simplify a title for matching: lowercase letters and digits only."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


YEAR = re.compile(r"(?<=[\s._(\[-])((?:19|20)\d\d)(?=[\s._)\]-]|$)")
SEASON_TAG = re.compile(r"[\s._-](?:S\d{1,2}(?:E\d{1,3})?|Season[\s._-]?\d{1,2})(?=[\s._-]|$)", re.I)


def parse_folder_name(name):
    """Split 'Movie.Title.2010.1080p.BluRay' or 'Movie Title (2010)' into (title, year).

    Uses the *last* year-like number, because titles can contain one too:
    'Blade.Runner.2049.2017.1080p' is 'Blade Runner 2049' from 2017.
    """
    # TV release names: drop everything from a season/episode tag onwards,
    # e.g. 'Breaking.Bad.S02.1080p' or 'Show Season 3' -> 'Breaking.Bad' / 'Show'.
    season = SEASON_TAG.search(name)
    if season:
        name = name[:season.start()]
    years = list(YEAR.finditer(name))
    if years:
        last = years[-1]
        return title_key(name[:last.start()]), int(last.group(1))
    return title_key(re.sub(r"\b(2160p|1080p|720p|480p)\b.*$", "", name, flags=re.I)), None


def suggest_match(folder_name, by_title):
    """Suggest which movie or show a stray folder probably is, or None.

    `by_title` maps title_key(title) -> [{"title": ..., "year": ..., "folder": ...}, ...].
    The suggestion includes "folder": where Radarr/Sonarr keeps that movie or show.
    """
    title, year = parse_folder_name(folder_name)
    candidates = by_title.get(title, [])
    if year:
        exact = [m for m in candidates if m["year"] == year]
        if exact:
            return {**exact[0], "confidence": "title + year"}
    if len(candidates) == 1:
        return {**candidates[0], "confidence": "title only"}
    return None


def file_entry(path, folder, tracked=False, app_file=None, app_name="Radarr"):
    """Describe one video file for the results page.

    `app_file` is the file's record from Radarr or Sonarr, if it tracks it.
    """
    entry = {
        "name": str(path.relative_to(folder)),
        "size": path.stat().st_size,
        "tracked": tracked,
        "keep": tracked,  # the file Radarr/Sonarr tracks starts as KEEP
    }
    if app_file:
        media = app_file.get("mediaInfo") or {}
        quality = ((app_file.get("quality") or {}).get("quality") or {})
        entry.update({
            "resolution": media.get("resolution") or (f"{quality['resolution']}p" if quality.get("resolution") else ""),
            "codec": media.get("videoCodec", ""),
            "source": quality.get("name", ""),
            "length": media.get("runTime", ""),
            "details_from": app_name,
        })
    else:
        entry.update(details_from_name(path.name), length="", details_from="file name")
    return entry


def folder_key(path):
    """A folder path in a form that's easy to compare (lowercase, forward slashes)."""
    return str(path).replace("\\", "/").rstrip("/").lower()


def find_strays(path_map, known_folders, by_title):
    """List folders and loose video files in the root folders that belong to
    no movie or show. Each gets a suggested match where one can be worked out.

    `known_folders` is a set of folder_key() values for every movie or show.
    """
    strays = []
    for local in path_map.values():
        if not local or not Path(local).is_dir():
            continue
        for entry in sorted(Path(local).iterdir(), key=lambda p: p.name.lower()):
            if entry.is_dir():
                if is_system_folder(entry.name) or folder_key(entry) in known_folders:
                    continue
                videos = video_files(entry)
                strays.append({
                    "name": entry.name,
                    "path": str(entry),
                    "kind": "folder" if videos else "empty folder",
                    "videos": len(videos),
                    "size": sum(v.stat().st_size for v in videos),
                    "details": details_from_name(entry.name),
                    "suggestion": suggest_match(entry.name, by_title),
                })
            elif entry.suffix.lower() in VIDEO_TYPES and not is_system_file(entry.name):
                strays.append({
                    "name": entry.name,
                    "path": str(entry),
                    "kind": "loose file",
                    "videos": 1,
                    "size": entry.stat().st_size,
                    "details": details_from_name(entry.name),
                    "suggestion": suggest_match(entry.stem, by_title),
                })
    return strays


def valid_media_results(data, counts):
    """Check a Movies or TV results file has the shape its page relies on."""
    return (
        isinstance(data, dict)
        and isinstance(data.get("scanned_at"), str)
        and isinstance(data.get("counts"), dict)
        and all(isinstance(data["counts"].get(k), int) for k in counts)
        and isinstance(data.get("groups"), list)
        and all(
            isinstance(group, dict) and isinstance(group.get("files"), list)
            and isinstance(group.get("title"), str)
            and all(isinstance(f, dict) and isinstance(f.get("name"), str)
                    and isinstance(f.get("size"), int) for f in group["files"])
            for group in data["groups"]
        )
        and isinstance(data.get("strays"), list)
        and all(isinstance(s, dict) and isinstance(s.get("name"), str)
                and isinstance(s.get("size"), int) and isinstance(s.get("details"), dict)
                for s in data["strays"])
        and isinstance(data.get("missing_folders"), list)
    )


def unmapped_reason(server_path, path_map):
    """Explain why a movie's or show's folder couldn't be checked."""
    lowered = server_path.replace("\\", "/").lower()
    for root, local in path_map.items():
        if lowered.startswith(root.replace("\\", "/").rstrip("/").lower()) and not local:
            return f"Its root folder {root} has no path for this computer in SETUP."
    return "It isn't inside any of the app's current root folders (an old location?)."


def folder_contents(folder):
    """Summarise what's in a folder: file count, total size, file types, any video?
    Also the first few file names (inside the folder), so you can see what would go."""
    count, size, types, has_video, names = 0, 0, set(), False, []
    for current, subfolders, files in os.walk(folder):
        for name in files:
            path = Path(current) / name
            try:
                size += path.stat().st_size
            except OSError:
                pass
            count += 1
            if len(names) < SHOW_NAMES:
                names.append(str(path.relative_to(folder)))
            suffix = path.suffix.lower() or "(no extension)"
            types.add(suffix)
            if suffix in VIDEO_TYPES and not is_extra(path) and not is_system_file(name):
                has_video = True
    return {"files": count, "size": size, "types": sorted(types), "has_video": has_video, "names": names}


SHOW_NAMES = 12  # file names listed per folder before "...and N more"
