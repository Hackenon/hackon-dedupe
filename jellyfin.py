"""Talk to Jellyfin (and Emby, which shares the same API).

A thin client in the shape of plex.py: validate the server, list its libraries,
and ask it to rescan after files move. Authenticates with an API key (made in
Jellyfin's Dashboard > API Keys) sent in the modern `Authorization: MediaBrowser` header (the legacy X-Emby-Token
header is off by default in Jellyfin 10.12+ and removed in 10.13). Uses only Python's built-in urllib,
so there's nothing extra to install.
"""

import json
import urllib.error
import urllib.request

TIMEOUT_SECONDS = 10
PRODUCT = "HackOn Photo & Video DeDupe"
DEVICE_ID = "hackon-photo-video-dedupe"

# Jellyfin/Emby library (CollectionType) -> what this app calls it.
COLLECTION_TYPES = {"movies": "Movies", "tvshows": "TV",
                    "homevideos": "Photos", "photos": "Photos"}


class JellyfinError(Exception):
    """A problem talking to Jellyfin, with a message that's safe to show on screen."""


class JellyfinAuthError(JellyfinError):
    """Jellyfin rejected the API key (it answered 401/403)."""


def normalize_url(url):
    """Accept '192.168.1.10:8096' as well as 'http://192.168.1.10:8096/'."""
    url = url.strip().rstrip("/")
    if url and "://" not in url:
        url = "http://" + url
    return url


def _auth_header(api_key):
    """Jellyfin's modern auth header for an API key. The older X-Emby-Token header
    is disabled by default in Jellyfin 10.12+ and removed in 10.13, so an API key
    must come through here. An API key needs no username; the token alone is enough."""
    return (f'MediaBrowser Client="{PRODUCT}", Device="{PRODUCT}", '
            f'DeviceId="{DEVICE_ID}", Version="1.0", Token="{api_key}"')


def _request(url, api_key, endpoint, method="GET", timeout=TIMEOUT_SECONDS):
    """Call one API endpoint and return the decoded JSON ({} for an empty body)."""
    base = normalize_url(url)
    if not base:
        raise JellyfinError("Enter Jellyfin's address first")
    if not api_key:
        raise JellyfinError("Enter Jellyfin's API key first")
    request = urllib.request.Request(
        f"{base}/{endpoint}",
        headers={"Authorization": _auth_header(api_key), "Accept": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise JellyfinAuthError("Jellyfin rejected the API key") from None
        if error.code == 404:
            raise JellyfinError("That address answered, but it doesn't look like Jellyfin") from None
        raise JellyfinError(f"Jellyfin answered with error {error.code}") from None
    except urllib.error.URLError as error:
        raise JellyfinError(f"Can't reach Jellyfin ({error.reason})") from None
    except (TimeoutError, OSError):
        raise JellyfinError("Can't reach Jellyfin (no answer)") from None
    except json.JSONDecodeError:
        raise JellyfinError("That address answered, but it doesn't look like Jellyfin") from None


def server_info(url, api_key):
    """Return (server name, version). Raises JellyfinError if unreachable or the key is bad."""
    data = _request(url, api_key, "System/Info")
    if not isinstance(data, dict) or "Version" not in data:
        raise JellyfinError("That address answered, but it doesn't look like Jellyfin")
    return data.get("ServerName", "Jellyfin"), data["Version"]


def _parse_libraries(folders):
    """Map Jellyfin's VirtualFolders JSON to this app's library shape
    [{key, title, type, folders}]. Pure function, so it's easy to test."""
    found = []
    for folder in folders or []:
        kind = COLLECTION_TYPES.get((folder.get("CollectionType") or "").lower())
        if not kind:
            continue
        found.append({
            "key": str(folder.get("ItemId") or folder.get("Name", "")),
            "title": folder.get("Name", "?"),
            "type": kind,
            "folders": [p for p in (folder.get("Locations") or []) if p],
        })
    return found


def libraries(url, api_key, timeout=TIMEOUT_SECONDS):
    """Return the Movies, TV and Photos libraries, each with the folders it uses."""
    data = _request(url, api_key, "Library/VirtualFolders", timeout=timeout)
    return _parse_libraries(data if isinstance(data, list) else [])


def refresh(url, api_key):
    """Ask Jellyfin to rescan every library. Jellyfin's API has no per-folder
    scan, so this triggers a full library refresh (it's incremental on its end)."""
    _request(url, api_key, "Library/Refresh", method="POST")
