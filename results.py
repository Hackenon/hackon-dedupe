"""Piece 4: run every check and save the results to results.json.

The web app reads this file instead of rescanning each time you open it.
"""

import sys
from datetime import datetime
from pathlib import Path

from cache import FingerprintCache
from exact import find_exact_duplicates
from near import best_first, find_near_duplicates
from safejson import read_json, write_json
from scan import scan, find_empty_folders

RESULTS_FILE = Path(__file__).parent / "results.json"


def file_info(path, folder, pixels=None, keep=False, best=False):
    """Describe one file as a plain dictionary (JSON can't store Path objects)."""
    return {
        "path": str(path.relative_to(folder)),
        "size": path.stat().st_size,
        "pixels": pixels,
        "keep": keep,
        "best": best,
    }


def run_scan(folder, progress=print, cache=None):
    """Run all three checks on `folder` and return the results as a dictionary."""
    folder = Path(folder)
    if cache is None:
        cache = FingerprintCache()
    progress(f"Scanning {folder}")
    photos, videos, skipped = scan(folder)
    progress(f"Found {len(photos)} photos, {len(videos)} videos, {len(skipped)} other files")

    groups = []

    # 1. Exact duplicates (photos and videos). Identical files are equally
    #    good, so keep the one with the shortest name: usually the original,
    #    not "photo (1).jpg".
    progress("Checking for exact duplicates")
    exact_groups = find_exact_duplicates(photos + videos, cache)
    extras = set()  # extra exact copies, left out of the look-alike check
    for group in exact_groups:
        group = sorted(group, key=lambda p: (len(p.name), str(p)))
        extras.update(group[1:])
        groups.append({
            "kind": "exact",
            "files": [file_info(p, folder, keep=(i == 0), best=(i == 0))
                      for i, p in enumerate(group)],
        })

    progress(f"{len(exact_groups)} exact duplicate groups")

    # 2. Look-alike photos. Copies: keep only the best. Similar shots: keep
    #    everything to start with; you untick the ones you don't want.
    remaining = [p for p in photos if p not in extras]
    copies, similar = find_near_duplicates(remaining, progress, cache)
    for kind, kind_groups in (("copy", copies), ("similar", similar)):
        for group in kind_groups:
            groups.append({
                "kind": kind,
                "files": [
                    file_info(path, folder, pixels,
                              keep=(i == 0 or kind == "similar"), best=(i == 0))
                    for i, (path, _, pixels) in enumerate(best_first(group))
                ],
            })

    progress(f"{len(copies)} copy groups, {len(similar)} similar-shot groups")

    for number, group in enumerate(groups, start=1):
        group["id"] = number

    cache.save()
    if cache.hits:
        progress(f"Reused {cache.hits} fingerprints from earlier scans")
    progress("Scan complete")
    return {
        "folder": str(folder.resolve()),
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "counts": {"photos": len(photos), "videos": len(videos), "skipped": len(skipped)},
        "groups": groups,
        "empty_folders": [{"name": p.name, "path": str(p)} for p in find_empty_folders(folder)],
    }


def save_results(results):
    write_json(RESULTS_FILE, results)


def valid_results(data):
    """Check results.json has the shape the pages rely on."""
    return (
        isinstance(data, dict)
        and isinstance(data.get("folder"), str)
        and isinstance(data.get("scanned_at"), str)
        and isinstance(data.get("counts"), dict)
        and all(isinstance(data["counts"].get(k), int) for k in ("photos", "videos", "skipped"))
        and isinstance(data.get("groups"), list)
        and all(
            isinstance(group, dict)
            and isinstance(group.get("id"), int)
            and group.get("kind") in ("exact", "copy", "similar")
            and isinstance(group.get("files"), list)
            and all(
                isinstance(file, dict)
                and isinstance(file.get("path"), str)
                and isinstance(file.get("size"), int)
                and isinstance(file.get("keep"), bool)
                for file in group["files"]
            )
            for group in data["groups"]
        )
    )


def load_results():
    """Return the saved results, or None if no scan has been run yet."""
    return read_json(RESULTS_FILE, default=lambda: None, valid=valid_results)


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python results.py FOLDER")

    folder = Path(sys.argv[1])
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")

    results = run_scan(folder)
    save_results(results)

    kinds = [group["kind"] for group in results["groups"]]
    print(f"\nExact duplicates: {kinds.count('exact')} groups")
    print(f"Copies:           {kinds.count('copy')} groups")
    print(f"Similar shots:    {kinds.count('similar')} groups")
    print(f"Saved to {RESULTS_FILE.name}")


if __name__ == "__main__":
    main()
