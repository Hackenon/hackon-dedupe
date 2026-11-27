# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Read missing video details (resolution, codec, length) with ffprobe.

ffprobe comes with FFmpeg; the app can download it for you (see ffmpegsetup.py). It reads a
file's header information without playing or converting it, so it's quick and
light on the CPU; most of the time is spent waiting on the network. Results
are cached, so each file is only read once unless it changes.
"""

import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cache import FingerprintCache
from mediatools import video_files

PROBE_TIMEOUT_SECONDS = 60
SIMULTANEOUS = 4  # files read at the same time; it's network-bound, not CPU-bound

CODEC_NAMES = {
    "h264": "x264", "hevc": "x265", "av1": "AV1", "vp9": "VP9", "mpeg4": "XviD/MPEG-4",
    "mpeg2video": "MPEG-2", "vc1": "VC-1", "wmv3": "WMV", "msmpeg4v3": "DivX 3",
}


def ffprobe_path():
    """Where ffprobe is: our own downloaded copy first, then anything on PATH."""
    from ffmpegsetup import bundled_ffprobe
    local = bundled_ffprobe()
    return str(local) if local else shutil.which("ffprobe")


def probe(path):
    """Return {"resolution", "codec", "length"} for one video, or None if unreadable."""
    command = [
        ffprobe_path(), "-v", "error",
        "-probesize", "10M", "-analyzeduration", "5M",  # cap how much is read
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height:format=duration",
        "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=PROBE_TIMEOUT_SECONDS)
        data = json.loads(result.stdout or "{}")
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    streams = data.get("streams") or []
    if not streams:
        return None
    stream = streams[0]
    seconds = float((data.get("format") or {}).get("duration") or 0)
    hours, rest = divmod(int(seconds), 3600)
    return {
        "resolution": f"{stream['width']}x{stream['height']}" if stream.get("width") else "",
        "codec": CODEC_NAMES.get(stream.get("codec_name", ""), (stream.get("codec_name") or "").upper()),
        "length": f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if seconds else "",
    }


def cached_probe(path, cache):
    value = cache.get("probe", path)
    if value is None:
        value = probe(path)
        if value is not None:
            cache.put("probe", path, value)
    return value


def missing(entry):
    return not (entry.get("resolution") and entry.get("codec") and entry.get("length"))


def files_needing_details(results):
    """List of (where to write, video path) for everything missing details.

    Extra copies are read directly. A stray folder gets the details of its
    largest video; a loose stray file is read itself.
    """
    todo = []
    for group in (results or {}).get("groups", []):
        for file in group["files"]:
            if not file.get("tracked") and missing(file):
                todo.append((file, Path(group["folder"]) / file["name"]))
    for stray in (results or {}).get("strays", []):
        if stray.get("videos") and missing(stray["details"]):
            todo.append((stray["details"], Path(stray["path"])))
    return todo


def count_needing_details(results):
    return len(files_needing_details(results))


def add_details(results, progress=print, cache=None):
    """Fill in missing details in `results` (changed in place). Returns how many were found."""
    if not ffprobe_path():
        raise RuntimeError("ffprobe not found. Use GET FFMPEG in Setup to add it.")
    cache = cache or FingerprintCache()
    todo = files_needing_details(results)
    progress(f"Reading details for {len(todo)} files with ffprobe")

    def work(item):
        target, path = item
        if path.is_dir():  # stray folder: use its largest video
            videos = video_files(path)
            if not videos:
                return target, None
            path = max(videos, key=lambda p: p.stat().st_size)
        return target, cached_probe(path, cache)

    found = 0
    with ThreadPoolExecutor(SIMULTANEOUS) as pool:
        for number, (target, details) in enumerate(pool.map(work, todo), start=1):
            if details:
                for key, value in details.items():
                    if value and not target.get(key):
                        target[key] = value
                target["details_from"] = "ffprobe"
                found += 1
            if number % 25 == 0:
                progress(f"Read {number} of {len(todo)}")
    cache.save()
    progress(f"Found details for {found} of {len(todo)} files")
    return found
