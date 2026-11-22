"""Piece 2: find files whose contents are exactly the same."""

import hashlib
import sys
from collections import defaultdict
from pathlib import Path

from scan import scan  # reuse piece 1

CHUNK_SIZE = 1024 * 1024  # read 1 MB at a time, like recover's 512-byte blocks


def fingerprint(path):
    """Return a SHA-256 fingerprint of a file's contents."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:  # "rb" = read bytes
        while chunk := f.read(CHUNK_SIZE):
            sha.update(chunk)
    return sha.hexdigest()


def cached_fingerprint(path, cache):
    """fingerprint(path), reusing a saved value when the file hasn't changed."""
    if cache is None:
        return fingerprint(path)
    value = cache.get("sha", path)
    if value is None:
        value = fingerprint(path)
        cache.put("sha", path, value)
    return value


def find_exact_duplicates(paths, cache=None):
    """Return a list of groups; each group is a list of identical files."""
    # Step 1: group by size. Different sizes can't be identical.
    by_size = defaultdict(list)
    for path in paths:
        by_size[path.stat().st_size].append(path)

    # Step 2: only fingerprint files that share a size with another file.
    by_fingerprint = defaultdict(list)
    for same_size in by_size.values():
        if len(same_size) < 2:
            continue
        for path in same_size:
            by_fingerprint[cached_fingerprint(path, cache)].append(path)

    # Step 3: any fingerprint with 2+ files is a duplicate group.
    return [group for group in by_fingerprint.values() if len(group) > 1]


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python exact.py FOLDER")

    folder = Path(sys.argv[1])
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")

    photos, videos, _ = scan(folder)
    groups = find_exact_duplicates(photos + videos)

    wasted = 0
    for number, group in enumerate(groups, start=1):
        size = group[0].stat().st_size
        wasted += size * (len(group) - 1)
        print(f"Group {number} ({size / 1_000_000:.1f} MB each):")
        for path in group:
            print(f"  {path.relative_to(folder)}")

    print(f"\n{len(groups)} duplicate groups, {wasted / 1_000_000:.1f} MB wasted")


if __name__ == "__main__":
    main()
