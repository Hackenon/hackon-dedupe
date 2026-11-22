"""Remember fingerprints between scans, so unchanged files aren't read again.

Reading 60 GB over the network takes a while. A file whose size and
modified time haven't changed since the last scan still has the same
contents, so its fingerprints are reused instead of recalculated.
"""

from pathlib import Path

from safejson import read_json, write_json

CACHE_FILE = Path(__file__).parent / "fingerprints.json"

# Bump this if the fingerprint math ever changes, so old entries are ignored.
VERSION = 1


class FingerprintCache:
    """A dictionary of fingerprints saved to disk.

    Each entry is keyed by the kind of fingerprint ("sha" or "look") and the
    file's full path, and stores the file's size and modified time alongside
    the value, so changed files are detected.
    """

    def __init__(self, path=CACHE_FILE):
        self.path = path
        self.entries = {}
        self.hits = 0
        saved = read_json(path, default=dict, valid=lambda d: isinstance(d, dict)
                          and isinstance(d.get("entries", {}), dict))
        if saved.get("version") == VERSION:
            self.entries = saved["entries"]

    def _key(self, kind, file):
        return f"{kind}|{Path(file).absolute()}"

    def get(self, kind, file):
        """Return the saved value, or None if missing or the file changed."""
        entry = self.entries.get(self._key(kind, file))
        if entry is None:
            return None
        stat = Path(file).stat()
        if entry["size"] != stat.st_size or entry["modified"] != stat.st_mtime:
            return None
        self.hits += 1
        return entry["value"]

    def put(self, kind, file, value):
        stat = Path(file).stat()
        self.entries[self._key(kind, file)] = {
            "size": stat.st_size, "modified": stat.st_mtime, "value": value,
        }

    def save(self):
        write_json(self.path, {"version": VERSION, "entries": self.entries}, indent=None)
