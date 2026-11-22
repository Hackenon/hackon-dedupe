"""Read a Radarr/Sonarr API key straight from the server, without a key.

This only works when that server is set to "Disabled for Local Addresses"
(Settings > General > Security > Authentication Required). With that on,
Radarr and Sonarr treat requests from the local network as already trusted
and hand out their own setup data, the API key included, with no sign-in.
This reads your own key from your own server over your own network; it fits
the same situation as the Plex backdoor and carries the same caveat.

Detection and reading only; it never changes the server's settings.

Removable: set ENABLED = False to switch it off everywhere (the button
disappears). To remove it completely, delete this file and the lines marked
"# apikey" in app.py and setup.html.
"""

import json
import re
import urllib.error
import urllib.request

import arr

ENABLED = True
TIMEOUT_SECONDS = 10

# Where the web app keeps the key it loads into your browser. The first that
# answers with a key wins.
PAGES = ("/initialize.json", "/initialize.js")
KEY_IN_JS = re.compile(r'apiKey["\']?\s*[:=]\s*["\']([0-9a-fA-F]{20,})["\']')


def _get(url, timeout=TIMEOUT_SECONDS):
    request = urllib.request.Request(url, headers={"Accept": "application/json, text/javascript"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", "replace")


def read_key(url, app="Radarr"):
    """Return the API key the server hands out without a sign-in, or None if it
    asks for one. Raises arr.ArrError if the server can't be reached."""
    url = arr.normalize_url(url)
    if not url:
        raise arr.ArrError(f"Enter {app}'s address first")
    for page in PAGES:
        try:
            status, body = _get(url + page)
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                return None  # the server wants a sign-in: the door is shut
            continue  # that page isn't there on this version; try the next
        except urllib.error.URLError as error:
            raise arr.ArrError(f"Can't reach {url} ({error.reason})") from None
        except (TimeoutError, OSError):
            raise arr.ArrError(f"Can't reach {url} (no answer)") from None
        if page.endswith(".json"):
            try:
                key = json.loads(body).get("apiKey")
            except json.JSONDecodeError:
                key = None
        else:
            match = KEY_IN_JS.search(body)
            key = match.group(1) if match else None
        if key:
            return key
    return None
