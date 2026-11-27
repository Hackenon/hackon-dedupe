# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Piece 1: scan a folder and count photos, videos, and files to skip."""

import os
import sys
from pathlib import Path

# Files moved here by the app are left out of future scans.
REVIEW_FOLDER = "_review"

# Folders that operating systems and NAS boxes create for themselves.
# Synology's @eaDir holds its own thumbnail JPGs, which would otherwise look
# like thousands of copies of your photos.
SYSTEM_FOLDERS = {
    REVIEW_FOLDER.lower(), "@eadir", "#recycle", "#snapshot",
    "$recycle.bin", "system volume information",
}

# System files: Windows thumbnail caches, Mac folder settings, Plex ignore lists.
SYSTEM_FILES = {"thumbs.db", "desktop.ini", ".ds_store", ".plexignore"}


def is_system_folder(name):
    """Hidden folders (starting with '.') and known system folders."""
    return name.startswith(".") or name.lower() in SYSTEM_FOLDERS


def is_system_file(name):
    """Known system files, and Mac '._name.jpg' sidecar files: they end in
    .jpg but aren't photos, and appear when Macs write to network drives."""
    return name.lower() in SYSTEM_FILES or name.startswith("._")

# File types we care about. Lowercase, so ".JPG" and ".jpg" both match.
PHOTO_TYPES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".gif", ".bmp", ".tif", ".tiff"}
VIDEO_TYPES = {".mov", ".mp4", ".m4v", ".avi", ".mkv"}


def scan(folder):
    """Sort every file under `folder` into photos, videos, and skipped.

    System files and folders are ignored completely.
    """
    folder = Path(folder)
    photos, videos, skipped = [], [], []

    # os.walk visits every subfolder. Removing names from `subfolders` tells
    # it not to go inside them, which saves time on a network drive.
    for current, subfolders, files in os.walk(folder):
        subfolders[:] = sorted(name for name in subfolders if not is_system_folder(name))

        for name in sorted(files):
            if is_system_file(name):
                continue
            path = Path(current) / name
            ext = path.suffix.lower()
            if ext in PHOTO_TYPES:
                photos.append(path)
            elif ext in VIDEO_TYPES:
                videos.append(path)
            else:
                skipped.append(path)

    return photos, videos, skipped


def folder_has_media(path):
    """True if any photo or video lives anywhere under `path`
    (system files and folders ignored)."""
    media = PHOTO_TYPES | VIDEO_TYPES
    for current, subfolders, files in os.walk(path):
        subfolders[:] = [s for s in subfolders if not is_system_folder(s)]
        for name in files:
            if not is_system_file(name) and Path(name).suffix.lower() in media:
                return True
    return False


def find_empty_folders(folder):
    """Sub-folders of `folder` whose whole subtree has no photo or video
    (system/_review folders ignored). Parents are listed before children."""
    folder = Path(folder)
    media = PHOTO_TYPES | VIDEO_TYPES
    walked = []
    for current, subfolders, files in os.walk(folder):
        subfolders[:] = sorted(s for s in subfolders if not is_system_folder(s))
        walked.append((Path(current), [n for n in files if not is_system_file(n)]))
    has_media = set()
    for cur, files in reversed(walked):       # deepest first
        if any(Path(n).suffix.lower() in media for n in files):
            p = cur
            while True:
                has_media.add(p)
                if p == folder:
                    break
                p = p.parent
    return [cur for cur, _ in walked if cur != folder and cur not in has_media]


def main():
    # Same pattern as CS50: check the command-line arguments first.
    if len(sys.argv) != 2:
        sys.exit("Usage: python scan.py FOLDER")

    folder = Path(sys.argv[1])
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")

    photos, videos, skipped = scan(folder)

    print(f"Photos:  {len(photos)}")
    print(f"Videos:  {len(videos)}")
    print(f"Skipped: {len(skipped)}")
    for path in skipped:
        print(f"  - {path.relative_to(folder)}")


if __name__ == "__main__":
    main()
