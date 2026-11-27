# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Play a media file so the user can identify it -- not a full media player.

Browser-friendly files (MP4/H.264, WebM) stream into an in-page frame. Anything
the browser can't decode falls back to VLC's own window, if VLC is installed. If
neither can play it, we remember the file as unplayable -- keyed by size + mtime,
so a file that later changes is tried again -- and its PLAY button greys out.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import paths

_REGISTRY = paths.user_data("unplayable.json")

# Extensions an HTML5 <video> can usually decode. Everything else goes to VLC.
# (A codec it still can't handle -- e.g. HEVC inside .mp4/.mov -- fires the
# <video> error event, and the page falls back to VLC from there.)
BROWSER_PLAYABLE = {".mp4", ".m4v", ".webm", ".ogg", ".ogv", ".mov"}


def browser_can_try(name):
    """True if it's worth letting the browser attempt this file in the frame."""
    return Path(name).suffix.lower() in BROWSER_PLAYABLE


# --------------------------------------------------------------- VLC detection
def _vlc_candidates():
    exe = shutil.which("vlc")
    if exe:
        yield exe
    if sys.platform.startswith("win"):
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
            if base:
                yield str(Path(base) / "VideoLAN" / "VLC" / "vlc.exe")
    elif sys.platform == "darwin":
        yield "/Applications/VLC.app/Contents/MacOS/VLC"


def vlc_path():
    """Path to a VLC we can launch, or None if VLC isn't installed."""
    for cand in _vlc_candidates():
        if cand and Path(cand).exists():
            return cand
    return None


def vlc_available():
    return vlc_path() is not None


def launch_vlc(file):
    """Open `file` in VLC's own window. True if VLC actually started."""
    exe = vlc_path()
    if not exe:
        return False
    try:
        subprocess.Popen(
            [exe, "--play-and-exit", str(file)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except OSError:
        return False


# ----------------------------------------------------------- unplayable memory
def _signature(path):
    """A file's identity: size + mtime. None if the file is gone."""
    try:
        st = Path(path).stat()
        return {"size": st.st_size, "mtime": int(st.st_mtime)}
    except OSError:
        return None


def _load():
    try:
        return json.loads(_REGISTRY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(data):
    try:
        _REGISTRY.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def mark_unplayable(path):
    """Remember that neither the browser nor VLC could play this file."""
    sig = _signature(path)
    if sig is None:
        return
    data = _load()
    data[str(path)] = sig
    _save(data)


def is_unplayable(path):
    """True only if this exact file (same size + mtime) was recorded unplayable.

    A changed file no longer matches its old signature, so it's offered again.
    """
    sig = _signature(path)
    if sig is None:
        return False
    return _load().get(str(path)) == sig
