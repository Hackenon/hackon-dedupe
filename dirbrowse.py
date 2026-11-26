"""List directories on this computer for the in-app folder browser.

The app can run headless on a server and be used from another machine's browser,
where a native OS folder dialog can't appear (it would only show on the server's
own screen). So folders are chosen through the web UI instead, which lists the
SERVER's directories -- read-only, directories only, never file contents.
"""

import os
import string
from pathlib import Path


def _drives():
    """Existing Windows drive roots, e.g. ['C:\\\\', 'D:\\\\']. Empty off Windows."""
    if os.name != "nt":
        return []
    return [f"{c}:\\" for c in string.ascii_uppercase if os.path.exists(f"{c}:\\")]


def _parent(p, drives):
    """The folder above `p`: a path, '' for a Windows drive root (-> drive list),
    or None at the POSIX filesystem root."""
    if p.parent == p:                       # a root
        return "" if drives else None
    return str(p.parent)


def list_dirs(path=None):
    """Return {path, parent, entries, drives[, error]} for a folder browser.

    `path` None/'' lists the roots (Windows drives, or '/' on POSIX). Otherwise it
    lists the immediate SUBDIRECTORIES of `path`, as entries [{name, path}] sorted
    case-insensitively; unreadable entries are skipped. `parent` is the folder
    above (or '' for a drive list, None at a root)."""
    drives = _drives()
    if not path:
        if drives:
            return {"path": "", "parent": None, "drives": drives,
                    "entries": [{"name": d, "path": d} for d in drives]}
        path = "/"                          # POSIX root

    p = Path(path)
    try:
        p = p.resolve()
    except OSError:
        pass

    entries = []
    try:
        with os.scandir(p) as it:
            for entry in it:
                try:
                    if entry.is_dir():
                        entries.append({"name": entry.name, "path": str(Path(entry.path))})
                except OSError:
                    continue                # unreadable entry: skip it
    except OSError as error:
        return {"path": str(p), "parent": _parent(p, drives), "drives": drives,
                "entries": [], "error": f"Can't open {p} ({error})"}

    entries.sort(key=lambda d: d["name"].lower())
    return {"path": str(p), "parent": _parent(p, drives), "drives": drives, "entries": entries}
