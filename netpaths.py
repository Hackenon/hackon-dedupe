"""Helpers for network paths like \\\\192.168.1.5\\Movies\\.

A NAS can have more than one address (for example a private link to the
server running Radarr, and a normal one for everything else). These helpers
find the address in a network path and swap it for another one.
"""

import ipaddress
import re
import socket
from pathlib import Path

# \\host\share\...  or  //host/share/...
NETWORK_PATH = re.compile(r"^(?P<slashes>[\\/]{2})(?P<host>[^\\/]+)(?P<rest>.*)$")


def network_host(path):
    """Return the server part of a network path, or None for local paths.

    network_host(r"\\\\10.0.0.5\\Movies") -> "10.0.0.5"
    network_host(r"M:\\Movies")          -> None
    """
    match = NETWORK_PATH.match(path or "")
    return match.group("host") if match else None


def swap_host(path, new_host):
    """Return `path` with its server address replaced by `new_host`.

    swap_host(r"\\\\10.0.0.5\\Movies", "192.168.1.5") -> r"\\\\192.168.1.5\\Movies"
    """
    match = NETWORK_PATH.match(path or "")
    if not match:
        return path
    new_host = new_host.strip().strip("\\/")
    return match.group("slashes") + new_host + match.group("rest")


def this_computer_address():
    """Return this computer's IPv4 address on the local network, or None.

    Connecting a UDP socket sends nothing over the network; it only asks the
    operating system which local address it would use to get there.
    """
    for target in ("192.168.0.1", "10.0.0.1", "8.8.8.8"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect((target, 9))
                address = ipaddress.IPv4Address(probe.getsockname()[0])
        except (OSError, ValueError):
            continue
        if not address.is_loopback and not address.is_unspecified:
            return str(address)
    try:
        address = ipaddress.IPv4Address(socket.gethostbyname(socket.gethostname()))
        if not address.is_loopback:
            return str(address)
    except (OSError, ValueError):
        pass
    return None


def network_prefix():
    """Return the first three numbers of this computer's address, e.g.
    "192.168.20", for hints like "192.168.20.x". None if unknown."""
    address = this_computer_address()
    return ".".join(address.split(".")[:3]) if address else None


def _normalized(path):
    """Lowercase, forward slashes, no trailing slash: for comparing paths."""
    return path.replace("\\", "/").rstrip("/").lower()


def translate(server_path, path_map):
    r"""Turn a path as Radarr sees it into the path this computer uses.

    path_map is {Radarr root folder: path on this computer}, from the setup
    screen. Returns None if the path isn't under a mapped root folder.

    translate(r"M:\Movies\Heat (1995)", {"M:\Movies": r"\\nas\Movies"})
        -> Path(r"\\nas\Movies\Heat (1995)")
    """
    if not server_path:
        return None
    wanted = _normalized(server_path)
    # Longest root first, so "M:\Movies 4K" wins over "M:\Movies".
    for root in sorted(path_map, key=len, reverse=True):
        local = path_map[root]
        root_normalized = _normalized(root)
        if not local or not (wanted == root_normalized or wanted.startswith(root_normalized + "/")):
            continue
        rest = server_path.replace("\\", "/").rstrip("/")[len(root_normalized):]
        parts = [part for part in rest.split("/") if part]
        return Path(local).joinpath(*parts)
    return None


def to_server_path(local_path, path_map):
    """The reverse of translate(): turn a path on this computer into the path
    the server (e.g. Plex) uses. Returns None if it isn't under a mapped folder."""
    wanted = _normalized(str(local_path))
    for server_root, local_root in sorted(path_map.items(), key=lambda item: len(item[1] or ""), reverse=True):
        if not local_root:
            continue
        local_normalized = _normalized(local_root)
        if not (wanted == local_normalized or wanted.startswith(local_normalized + "/")):
            continue
        rest = str(local_path).replace("\\", "/").rstrip("/")[len(local_normalized):]
        parts = [part for part in rest.split("/") if part]
        separator = "\\" if "\\" in server_root else "/"
        return server_root.rstrip("\\/") + "".join(separator + part for part in parts)
    return None
