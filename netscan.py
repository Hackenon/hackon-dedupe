"""Discovery: find the media apps HackOn knows about on this computer's own
network -- Radarr, Sonarr and Plex (supported today), and Jellyfin, Emby,
Medusa and SickGear (detected and reported as "not yet supported").

A deliberate, button-only sweep of the local /24 (e.g. 192.168.20.1-254) on
just the ports this app supports. It never scans anything wider, never runs on
its own, and only reports what answers; the user picks what to use.

Where a Radarr/Sonarr server is set to "Disabled for Local Addresses" it also
reads the API key the same way the GRAB KEY button does. That it can is a sign
the server trusts the whole local network; the page explains how to lock it down.

Removable: set ENABLED = False to hide the button. To delete it, remove this
file and the lines marked "# netscan" in app.py and setup.html.
"""

import json
import socket
import time
import urllib.error
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import arr
import arrkey
import providers
from netpaths import this_computer_address

ENABLED = True

CONNECT_TIMEOUT = 0.4   # seconds to wait for a port to answer
HTTP_TIMEOUT = 3        # seconds to confirm a service once its port is open
MAX_WORKERS = 64

# What we look for, and on which port. The port tells Radarr from Sonarr.
TARGETS = [
    {"service": "radarr", "name": "Radarr", "port": 7878, "kind": "arr", "status": "available"},
    {"service": "sonarr", "name": "Sonarr", "port": 8989, "kind": "arr", "status": "available"},
    {"service": "plex", "name": "Plex", "port": 32400, "kind": "plex", "status": "available"},
    # Known but not yet supported -- detected so the user sees them on the roadmap.
    {"service": "jellyfin_emby", "name": "Jellyfin/Emby", "port": 8096, "kind": "emby_api", "status": "planned"},
    {"service": "medusa_sickgear", "name": "Medusa/SickGear", "port": 8081, "kind": "medusa_html", "status": "planned"},
]


def local_prefix():
    """This computer's /24 prefix, e.g. '192.168.20', or None if unknown."""
    address = this_computer_address()
    if not address:
        return None
    parts = address.split(".")
    return ".".join(parts[:3]) if len(parts) == 4 else None


def _port_latency(host, port):
    """Milliseconds to open the port, or None if it doesn't answer. The time
    is just how long our own connection took; nothing extra is sent. It's a
    fair "which address is faster" signal when a server has two of them."""
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT):
            return (time.monotonic() - start) * 1000
    except OSError:
        return None


def _confirm_arr(url, name):
    """Return (is_it, api_key_or_None). Tries to read the key; if the server
    wants auth it's still Radarr/Sonarr, just without a key."""
    try:
        key = arrkey.read_key(url, name)
    except arr.ArrError:
        key = None
    if key:
        return True, key
    # No key handed out: a 401 from the API still proves it's there.
    try:
        request = urllib.request.Request(f"{url}/api/v3/system/status")
        urllib.request.urlopen(request, timeout=HTTP_TIMEOUT)
        return True, None
    except urllib.error.HTTPError as error:
        return error.code in (401, 403), None
    except (urllib.error.URLError, OSError):
        return False, None


def _confirm_plex(url):
    """Return Plex's machine id (proof it's Plex, and the same id at a second
    address means the same server), or None. /identity needs no sign-in."""
    try:
        request = urllib.request.Request(f"{url}/identity", headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            body = response.read().decode("utf-8", "replace")
        try:
            machine = json.loads(body).get("MediaContainer", {}).get("machineIdentifier")
            if machine:
                return machine
        except json.JSONDecodeError:
            pass
        match = re.search(r'machineIdentifier["\']?\s*[:=]\s*["\']([^"\']+)', body)
        return match.group(1) if match else None
    except (urllib.error.URLError, OSError):
        return None


def _confirm_emby(url):
    """Identify a Jellyfin or Emby server from its public info endpoint (no sign-in
    needed). Returns (service, display_name, server_id) or None."""
    try:
        request = urllib.request.Request(f"{url}/System/Info/Public",
                                         headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None
    product = (data.get("ProductName") or "").lower()
    server_id = data.get("Id") or ""
    if "emby" in product:
        return "emby", "Emby", server_id
    if "jellyfin" in product:
        return "jellyfin", "Jellyfin", server_id
    if data.get("Version") and ("ServerName" in data or "StartupWizardCompleted" in data):
        return "jellyfin", "Jellyfin", server_id
    return None


def _confirm_medusa(url):
    """Best-effort identify Medusa or SickGear from its login page. Returns
    (service, display_name) or None."""
    try:
        request = urllib.request.Request(f"{url}/", headers={"Accept": "text/html"})
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            body = response.read(8192).decode("utf-8", "replace").lower()
    except (urllib.error.URLError, OSError, TimeoutError):
        return None
    if "medusa" in body:
        return "medusa", "Medusa"
    if "sickgear" in body:
        return "sickgear", "SickGear"
    if "sickrage" in body or "sickbeard" in body:
        return "sickgear", "SickGear"
    return None


def _check(host, target):
    """Return a discovery dict if `target` is running at `host`, else None.
    `machine` identifies the instance so two addresses of one server group."""
    latency = _port_latency(host, target["port"])
    if latency is None:
        return None
    url = f"http://{host}:{target['port']}"
    kind = target["kind"]
    if kind == "arr":
        found, key = _confirm_arr(url, target["name"])
        if not found:
            return None
        # Same API key at two addresses => the same Radarr/Sonarr. With no key
        # we can't prove it, so each address stands on its own.
        machine = f"{target['service']}:{key}" if key else f"{target['service']}@{url}"
        return {"service": target["service"], "name": target["name"], "machine": machine,
                "url": url, "api_key": key or "", "has_key": bool(key), "ms": round(latency),
                "supported": True, "status": "available"}
    if kind == "plex":
        plex_machine = _confirm_plex(url)
        if plex_machine:
            return {"service": target["service"], "name": target["name"], "machine": f"plex:{plex_machine}",
                    "url": url, "api_key": "", "has_key": False, "ms": round(latency),
                    "supported": True, "status": "available"}
        return None
    if kind == "emby_api":
        info = _confirm_emby(url)
        if not info:
            return None
        service, name, server_id = info
        avail = providers.is_available(service)
        machine = f"{service}:{server_id}" if server_id else f"{service}@{url}"
        return {"service": service, "name": name, "machine": machine,
                "url": url, "api_key": "", "has_key": False, "ms": round(latency),
                "supported": avail, "status": "available" if avail else "planned"}
    if kind == "medusa_html":
        info = _confirm_medusa(url)
        if not info:
            return None
        service, name = info
        avail = providers.is_available(service)
        return {"service": service, "name": name, "machine": f"{service}@{url}",
                "url": url, "api_key": "", "has_key": False, "ms": round(latency),
                "supported": avail, "status": "available" if avail else "planned"}
    return None


def scan(prefix=None, hosts=None):
    """Sweep the local /24 for the supported services. Returns
    {"prefix": "192.168.20", "found": [discovery, ...]} or an error dict.

    `prefix`/`hosts` are for tests; normally both are worked out here.
    """
    prefix = prefix or local_prefix()
    if not prefix:
        return {"error": "Couldn't work out this computer's network address."}
    host_numbers = hosts if hosts is not None else range(1, 255)
    jobs = [(f"{prefix}.{n}", target) for n in host_numbers for target in TARGETS]
    discoveries = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for result in pool.map(lambda job: _check(*job), jobs):
            if result:
                discoveries.append(result)
    return {"prefix": prefix, "groups": _group(discoveries)}


def _group(discoveries):
    """Fold the responders into one group per instance. Each group lists its
    addresses fastest first, and when there's more than one the fastest is
    marked preferred."""
    groups = {}
    for d in discoveries:
        groups.setdefault((d["service"], d["machine"]), []).append(d)
    out = []
    for (service, _), addresses in groups.items():
        addresses.sort(key=lambda a: a["ms"])
        rows = [{"url": a["url"], "has_key": a["has_key"], "api_key": a["api_key"],
                 "ms": a["ms"], "preferred": False} for a in addresses]
        if len(rows) > 1:
            rows[0]["preferred"] = True  # fastest to answer
        out.append({"service": service, "name": addresses[0]["name"], "addresses": rows,
                    "supported": addresses[0].get("supported", True),
                    "status": addresses[0].get("status", "available")})
    out.sort(key=lambda g: (not g["supported"], g["name"], g["addresses"][0]["url"]))
    return out
