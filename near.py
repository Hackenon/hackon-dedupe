"""Piece 3: find photos that look almost the same.

Two lists:
  copies  - the same photo saved again (resized, re-saved, re-downloaded)
  similar - back-to-back or burst shots, for you to pick favorites
"""

import sys
from collections import defaultdict
from pathlib import Path

import imagehash
from PIL import Image, ImageOps, UnidentifiedImageError

try:  # optional .HEIC/.HEIF support; needs pillow-heif
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

import errorlog

# Problems that mean "this file isn't a readable photo", not a bug in the app.
UNREADABLE = (OSError, UnidentifiedImageError, ValueError, SyntaxError, Image.DecompressionBombError)

from scan import scan  # reuse piece 1

# How many of the 64 fingerprint bits may differ. Lower = stricter.
# Measured on your test photos: resized copies scored 0, burst shots 2 to 6.
COPY_DISTANCE = 0
SIMILAR_DISTANCE = 6


def look_fingerprint(path):
    """Return (fingerprint, pixel_count) describing what a photo looks like."""
    with Image.open(path) as img:
        width, height = img.size
        img.draft("RGB", (256, 256))        # JPEG speed-up: decode a small version
        img = ImageOps.exif_transpose(img)  # undo phone rotation flags
        fp = int(str(imagehash.phash(img)), 16)  # 64-bit number
    return fp, width * height


def distance(a, b):
    """Count the bits that differ between two fingerprints."""
    return (a ^ b).bit_count()  # ^ = XOR: 1 wherever the bits differ


def cached_look_fingerprint(path, cache):
    """look_fingerprint(path), reusing a saved value when the file hasn't changed."""
    if cache is None:
        return look_fingerprint(path)
    value = cache.get("look", path)
    if value is None:
        value = look_fingerprint(path)
        cache.put("look", path, list(value))
    return tuple(value)


def fingerprint_all(paths, progress=print, cache=None):
    """Return a list of (path, fingerprint, pixel_count) for every readable photo.

    `progress` is a function that receives status messages. It's print by
    default; the web app will pass its own so it can show a progress bar.
    """
    photos = []
    for number, path in enumerate(paths, start=1):
        if number % 100 == 0:
            progress(f"Fingerprinting {number} of {len(paths)}")
        try:
            fp, pixels = cached_look_fingerprint(path, cache)
            photos.append((path, fp, pixels))
        except UNREADABLE as error:  # a damaged or unsupported photo: expected
            progress(f"Couldn't read {path.name}: {error}")
        except Exception as error:   # anything else is a bug: log it, skip the photo, carry on
            # Every one is logged; the same error again is added to the same log.
            errorlog.record_error("fingerprinting photos (scan continued)", error,
                                  recent_log=[f"Photo: {path.name}"])
            progress(f"Couldn't read {path.name}: unexpected error (logged)")
    return photos


def group_look_alikes(photos, max_distance):
    """Return groups of photos whose fingerprints are within max_distance."""
    # If A looks like B and B looks like C, all three end up in one group.
    # leader[i] points toward the first member of photo i's group.
    leader = list(range(len(photos)))

    def find_leader(i):
        while leader[i] != i:
            i = leader[i]
        return i

    for i in range(len(photos)):
        for j in range(i + 1, len(photos)):
            if distance(photos[i][1], photos[j][1]) <= max_distance:
                leader[find_leader(j)] = find_leader(i)

    groups = defaultdict(list)
    for i, photo in enumerate(photos):
        groups[find_leader(i)].append(photo)
    return [group for group in groups.values() if len(group) > 1]


def best_first(group):
    """Sort a group so the best-quality copy comes first."""
    return sorted(group, key=lambda p: (p[2], p[0].stat().st_size), reverse=True)


def find_near_duplicates(paths, progress=print, cache=None):
    """Return (copies, similar): two lists of groups."""
    progress(f"Fingerprinting {len(paths)} photos")
    photos = fingerprint_all(paths, progress, cache)
    progress("Comparing fingerprints")
    copies = group_look_alikes(photos, COPY_DISTANCE)
    similar = [
        group for group in group_look_alikes(photos, SIMILAR_DISTANCE)
        if len({fp for _, fp, _ in group}) > 1  # skip groups that are all copies
    ]
    return copies, similar


def print_groups(title, groups, folder, keep_label):
    print(f"\n=== {title}: {len(groups)} groups ===")
    for number, group in enumerate(groups, start=1):
        print(f"\nGroup {number}:")
        for rank, (path, _, pixels) in enumerate(best_first(group)):
            label = keep_label if rank == 0 else " " * len(keep_label)
            mb = path.stat().st_size / 1_000_000
            print(f"  {label} {path.relative_to(folder)}  "
                  f"({pixels / 1_000_000:.1f} MP, {mb:.1f} MB)")


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python near.py FOLDER")

    folder = Path(sys.argv[1])
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")

    photos, _, _ = scan(folder)
    print(f"Fingerprinting {len(photos)} photos...")
    copies, similar = find_near_duplicates(photos)

    print_groups("Copies", copies, folder, keep_label="KEEP")
    print_groups("Similar shots (you choose)", similar, folder, keep_label="BEST")


if __name__ == "__main__":
    main()
