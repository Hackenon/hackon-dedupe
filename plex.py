"""Talk to Plex: sign in with a PIN, list libraries, and (later) ask for rescans.

Sign-in uses Plex's PIN flow for third-party apps: the app asks plex.tv for a
one-time code, you approve it on Plex's own website, and Plex hands the app
an access token. Your Plex password never goes into this app.
Uses only Python's built-in urllib, so there's nothing extra to install.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

PLEX_TV = "https://plex.tv"            # Plex's account service
PLEX_AUTH_PAGE = "https://app.plex.tv/auth#?"
PRODUCT = "HackOn Photo & Video DeDupe"
TIMEOUT_SECONDS = 10

# The Plex library types this app works with, and what to call them.
LIBRARY_TYPES = {"photo": "Photos", "movie": "Movies", "show": "TV"}


class PlexError(Exception):
    """A problem talking to Plex, with a message that's safe to show on screen."""


class PlexAuthError(PlexError):
    """Plex wants a sign-in (it answered 401)."""


def normalize_url(url):
    """Accept '192.168.1.10:32400' as well as 'http://192.168.1.10:32400/'."""
    url = url.strip().rstrip("/")
    if url and "://" not in url:
        url = "http://" + url
    return url


def _request(url, client_id, token=None, method="GET", what="Plex", timeout=TIMEOUT_SECONDS):
    headers = {
        "Accept": "application/json",
        "X-Plex-Product": PRODUCT,
        "X-Plex-Client-Identifier": client_id,
    }
    if token:
        headers["X-Plex-Token"] = token
    request = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as error:
        if error.code == 401:
            raise PlexAuthError(f"{what} rejected the sign-in. Try SIGN IN WITH PLEX again.") from None
        raise PlexError(f"{what} answered with error {error.code}") from None
    except urllib.error.URLError as error:
        raise PlexError(f"Can't reach {what} ({error.reason})") from None
    except (TimeoutError, OSError):
        raise PlexError(f"Can't reach {what} (no answer)") from None
    except json.JSONDecodeError:
        raise PlexError(f"That address answered, but it doesn't look like {what}") from None


# ------------------------------------------------------------ PIN sign-in

def start_pin(client_id):
    """Ask plex.tv for a one-time PIN. Returns (pin_id, page_to_approve_it)."""
    data = _request(f"{PLEX_TV}/api/v2/pins?strong=true", client_id, method="POST", what="plex.tv")
    if "id" not in data or "code" not in data:
        raise PlexError("plex.tv didn't return a sign-in code")
    page = PLEX_AUTH_PAGE + urllib.parse.urlencode({
        "clientID": client_id,
        "code": data["code"],
        "context[device][product]": PRODUCT,
    })
    return data["id"], page


def check_pin(client_id, pin_id):
    """Return the access token once you've approved the PIN, otherwise None."""
    data = _request(f"{PLEX_TV}/api/v2/pins/{int(pin_id)}", client_id, what="plex.tv")
    return data.get("authToken") or None


# ------------------------------------------------------------ your Plex server

def server_info(url, client_id, token):
    """Return (server name, version)."""
    url = normalize_url(url)
    if not url:
        raise PlexError("Enter your Plex server's address first")
    container = _request(f"{url}/", client_id, token).get("MediaContainer", {})
    if "version" not in container:
        raise PlexError("That address answered, but it doesn't look like a Plex server")
    return container.get("friendlyName", "Plex"), container["version"]


def libraries(url, client_id, token, timeout=TIMEOUT_SECONDS):
    """Return the Photos, Movies and TV libraries with the folders each uses."""
    container = _request(f"{normalize_url(url)}/library/sections", client_id, token, timeout=timeout).get("MediaContainer", {})
    found = []
    for section in container.get("Directory", []):
        if section.get("type") not in LIBRARY_TYPES:
            continue
        found.append({
            "key": str(section.get("key")),
            "title": section.get("title", "?"),
            "type": LIBRARY_TYPES[section["type"]],
            "folders": [location["path"] for location in section.get("Location", []) if location.get("path")],
        })
    return found


def refresh(url, client_id, token, section_key, path=None):
    """Ask Plex to rescan one library, or just one folder inside it.

    Plex only accepts a path that is one of the library's folders, or inside one.
    """
    query = "?" + urllib.parse.urlencode({"path": path}) if path else ""
    _request(f"{normalize_url(url)}/library/sections/{section_key}/refresh{query}", client_id, token)
