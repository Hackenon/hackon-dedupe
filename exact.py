"""Piece 2: find files whose contents are exactly the same."""

import hashlib
import sys
import time
from collections import defaultdict
from pathlib import Path

from scan import scan  # reuse piece 1
try:
    import perf
except Exception:  # standalone use (exact.py CLI) without the app's helpers
    perf = None

CHUNK_SIZE = 1024 * 1024  # read 1 MB at a time, like recover's 512-byte blocks
SAMPLE_BYTES = 50 * 1024 * 1024       # sampled mode reads 50 MB from each end
SAMPLE_THRESHOLD = 2 * SAMPLE_BYTES   # files this size or smaller are read in full


def fingerprint(path):
    """Return a SHA-256 fingerprint of a file's contents."""
    sha = hashlib.sha256()
    with open(path, "rb") as f:  # "rb" = read bytes
        while chunk := f.read(CHUNK_SIZE):
            sha.update(chunk)
    return sha.hexdigest()


def _hash_span(handle, sha, nbytes):
    """Feed up to `nbytes` from the current position of `handle` into `sha`."""
    remaining = nbytes
    while remaining > 0:
        chunk = handle.read(min(CHUNK_SIZE, remaining))
        if not chunk:
            break
        sha.update(chunk)
        remaining -= len(chunk)


def sampled_fingerprint(path, size=None):
    """A fast fingerprint: SHA-256 of a size tag plus the first and last 50 MB.

    For a file of 100 MB or less this reads the whole thing, so it is a full
    content hash; above that it samples head and tail to stay quick on large
    videos over a network share. Two files that match here are *very likely*
    identical, but only a full hash proves it -- see find_exact_duplicates(sample).
    """
    if size is None:
        size = path.stat().st_size
    sha = hashlib.sha256()
    sha.update(f"{size}:".encode("ascii"))  # self-describing; never collide across sizes
    with open(path, "rb") as f:
        if size <= SAMPLE_THRESHOLD:
            while chunk := f.read(CHUNK_SIZE):
                sha.update(chunk)
        else:
            _hash_span(f, sha, SAMPLE_BYTES)   # first 50 MB
            f.seek(size - SAMPLE_BYTES)
            _hash_span(f, sha, SAMPLE_BYTES)   # last 50 MB
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


def find_exact_duplicates(paths, cache=None, progress=None, sample=False):
    """Return a list of groups; each group is a list of (likely-)identical files.

    Only files that share a size with another are hashed -- different sizes can't
    be identical. `sample=True` uses sampled_fingerprint (head + tail of big
    files) for speed; a match is then "very likely identical", confirmed only by
    a full hash. `sample=False` reads whole files (certain, slower). Every file
    actually read is reported through `progress`; cached files stay quiet."""
    # Step 1: group by size. Different sizes can't be identical.
    by_size = defaultdict(list)
    for path in paths:
        by_size[path.stat().st_size].append(path)

    # Step 2: only fingerprint files that share a size with another file.
    kind = "sha-sample" if sample else "sha"
    by_fingerprint = defaultdict(list)
    start, bytes_read = time.perf_counter(), 0
    for size, same_size in by_size.items():
        if len(same_size) < 2:
            continue
        for path in same_size:
            value = cache.get(kind, path) if cache is not None else None
            if value is None:  # not cached: read and hash it (the slow part)
                if progress:
                    note = " [first+last 50MB]" if (sample and size > SAMPLE_THRESHOLD) else ""
                    progress(f"Hashing {path.name} ({size / 1_000_000:.0f} MB){note}")
                value = sampled_fingerprint(path, size) if sample else fingerprint(path)
                bytes_read += size if (not sample or size <= SAMPLE_THRESHOLD) else 2 * SAMPLE_BYTES
                if cache is not None:
                    cache.put(kind, path, value)
            by_fingerprint[value].append(path)

    if perf is not None and bytes_read:  # learn this computer's read speed
        perf.record(bytes_read, time.perf_counter() - start)

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
