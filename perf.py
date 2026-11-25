"""Remember how fast this computer reads media, to estimate full-hash times.

A full verify (or a full-content scan) has to read whole files, which is slow
over a network share. We fold each observed read speed into a saved moving
average so the UI can show a realistic "~N min" estimate before you commit to it.
"""

import paths
from safejson import read_json, write_json

PERF_FILE = paths.user_data("perf.json")
DEFAULT_MBPS = 40.0  # a cautious guess before anything has been measured


def _load():
    return read_json(PERF_FILE, default=dict, valid=lambda d: isinstance(d, dict))


def record(bytes_read, seconds):
    """Fold an observed read throughput (bytes over seconds) into the average."""
    if bytes_read <= 0 or seconds <= 0:
        return
    mbps = (bytes_read / 1_000_000) / seconds
    data = _load()
    prev = data.get("read_mbps")
    data["read_mbps"] = round(mbps if prev is None else 0.7 * prev + 0.3 * mbps, 2)
    write_json(PERF_FILE, data)


def read_mbps():
    """The saved average read speed in MB/s, or a cautious default."""
    return _load().get("read_mbps") or DEFAULT_MBPS


def estimate_label(total_bytes):
    """A short human estimate of how long reading `total_bytes` would take."""
    seconds = total_bytes / (read_mbps() * 1_000_000)
    when = f"~{max(1, round(seconds))}s" if seconds < 90 else f"~{round(seconds / 60)}m"
    return f"{when} to full-hash {total_bytes / 1_000_000_000:.1f} GB"
