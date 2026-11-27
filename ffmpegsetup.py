# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Fetch ffprobe for the user, so nobody has to install part of the app by hand.

We only ever run **ffprobe** (it reads a video's metadata — resolution, codec,
length — without decoding), so an **LGPL** build is all we need. That avoids the
GPL-only encoders (x264/x265) entirely and keeps the licensing simple.

The binary lives in the app's own `bin/` folder, found before anything on PATH,
next to the FFmpeg licence and a NOTICE as the LGPL asks. Nothing is installed
system-wide: no admin rights, no winget, no Homebrew.

Windows is wired up now (BtbN's explicit LGPL static build). macOS auto-download
waits until there's a verified LGPL arm64 build to point at; until then a Mac
falls back to a system ffprobe on PATH.
"""

import hashlib
import os
import platform
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path
import paths

BIN_DIR = paths.user_data("bin")
EXE = "ffprobe.exe" if os.name == "nt" else "ffprobe"

# LGPL builds only (no GPL-only encoders; we just read metadata).
SOURCES = {
    "win64": {
        "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-lgpl.zip",
        "sha_url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-lgpl.zip.sha256",
        "member": "ffprobe.exe",
        "source": "BtbN FFmpeg-Builds (LGPL static variant)",
        "size_hint": "about 35 MB",
    },
    # "macos": pending a verified LGPL arm64 build; see docs/ffmpeg-bundling.md
}


class FFmpegError(RuntimeError):
    """A download/extract problem worth showing the user (not a code bug)."""


def platform_key():
    if os.name == "nt":
        return "win64"
    if platform.system() == "Darwin":
        return "macos"
    return None


def bundled_ffprobe():
    """The ffprobe we downloaded into the app, or None."""
    path = BIN_DIR / EXE
    return path if path.exists() else None


def can_download():
    """True when this platform has an automatic LGPL source wired up."""
    return platform_key() in SOURCES


def size_hint():
    src = SOURCES.get(platform_key())
    return src["size_hint"] if src else ""


def _download(url, dest, progress):
    progress("Downloading " + url.rsplit("/", 1)[-1] + " ...")
    req = urllib.request.Request(url, headers={"User-Agent": "HackOn-DeDupe"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        got = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if total:
                    progress("  %d / %d MB" % (got // 1048576, total // 1048576))
    return dest


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _extract(archive, member, progress):
    """Pull just the ffprobe binary (and any licence file) out of a .zip."""
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        target = next((n for n in names
                       if n.replace("\\", "/").endswith("/" + member) or n == member), None)
        if target is None:
            raise FFmpegError("ffprobe wasn't inside the download.")
        BIN_DIR.mkdir(exist_ok=True)
        with z.open(target) as s, open(BIN_DIR / EXE, "wb") as d:
            shutil.copyfileobj(s, d)
        # keep the licence alongside the binary (LGPL compliance)
        for n in names:
            base = n.replace("\\", "/").rsplit("/", 1)[-1].upper()
            if base in ("LICENSE", "LICENSE.TXT", "COPYING.LGPLV2.1", "COPYING"):
                with z.open(n) as s, open(BIN_DIR / "FFMPEG-LICENSE.txt", "wb") as d:
                    shutil.copyfileobj(s, d)
                break


def download(progress=print):
    """Fetch an LGPL ffprobe for this platform into BIN_DIR. Returns its path."""
    key = platform_key()
    if key not in SOURCES:
        raise FFmpegError("Automatic download isn't available on this system yet. "
                          "Install FFmpeg and it'll be found on PATH.")
    src = SOURCES[key]
    with tempfile.TemporaryDirectory() as tmp:
        try:
            archive = _download(src["url"], Path(tmp) / "ffmpeg.zip", progress)
        except OSError as error:  # no internet, source down, etc. -- expected, not a bug
            raise FFmpegError("Couldn't download ffprobe (%s). Check your internet "
                              "connection and try again." % error)

        if src.get("sha_url"):
            try:
                req = urllib.request.Request(src["sha_url"], headers={"User-Agent": "HackOn-DeDupe"})
                want = urllib.request.urlopen(req, timeout=30).read().decode().split()[0].strip().lower()
            except Exception:
                want = ""
                progress("Couldn't fetch the checksum; continuing")
            if want:
                if _sha256(archive) != want:
                    raise FFmpegError("The download failed its checksum check; nothing was installed.")
                progress("Checksum OK")

        progress("Extracting ffprobe ...")
        _extract(archive, src["member"], progress)

    path = BIN_DIR / EXE
    if not path.exists():
        raise FFmpegError("The download didn't contain ffprobe.")
    if os.name != "nt":
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    (BIN_DIR / "NOTICE.txt").write_text(
        "ffprobe here is from the FFmpeg project, used unmodified under the LGPL v2.1.\n"
        "Build: " + src["source"] + "\n"
        "Download: " + src["url"] + "\n"
        "FFmpeg project and source: https://ffmpeg.org\n",
        encoding="utf-8")

    try:
        out = subprocess.run([str(path), "-version"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise FFmpegError("ffprobe downloaded but wouldn't run (%s)." % error)
    if out.returncode != 0:
        raise FFmpegError("ffprobe downloaded but wouldn't run.")
    first = (out.stdout.splitlines() or [""])[0]
    progress("Ready: " + first)
    return path
