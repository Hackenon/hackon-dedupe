"""Talk to Radarr and Sonarr through their APIs (version 3).

Radarr (movies) and Sonarr (TV) are built the same way, so one set of
functions works for both. Uses only Python's built-in urllib, so there's
nothing extra to install. Every request sends the API key in the X-Api-Key
header.
"""

import json
import urllib.error
import urllib.request

TIMEOUT_SECONDS = 10


class ArrError(Exception):
    """A problem talking to Radarr or Sonarr, with a message that's safe to show on screen."""


def normalize_url(url):
    """Accept '192.168.1.10:7878' as well as 'http://192.168.1.10:7878/'."""
    url = url.strip().rstrip("/")
    if url and "://" not in url:
        url = "http://" + url
    return url


def call(url, api_key, endpoint, app="Radarr", body=None):
    """Call one API endpoint and return the decoded JSON. `app` is only used in messages.

    With `body` (a dictionary) it's a POST sending that body as JSON; otherwise a GET.
    """
    url = normalize_url(url)
    if not url:
        raise ArrError(f"Enter {app}'s address first")
    if not api_key:
        raise ArrError(f"Enter {app}'s API key first")

    request = urllib.request.Request(
        f"{url}/api/v3/{endpoint}",
        headers={"X-Api-Key": api_key, "Accept": "application/json",
                 "Content-Type": "application/json"},
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 401:
            raise ArrError(f"{app} rejected the API key") from None
        if error.code == 404:
            raise ArrError(f"That address answered, but it doesn't look like {app}") from None
        raise ArrError(f"{app} answered with error {error.code}") from None
    except urllib.error.URLError as error:
        raise ArrError(f"Can't reach {url} ({error.reason})") from None
    except (TimeoutError, OSError):
        raise ArrError(f"Can't reach {url} (no answer)") from None
    except json.JSONDecodeError:
        raise ArrError(f"That address answered, but it doesn't look like {app}") from None


def status(url, api_key, app="Radarr"):
    """Return the app's status (name, version); raises ArrError if unreachable."""
    data = call(url, api_key, "system/status", app)
    if not isinstance(data, dict) or "version" not in data:
        raise ArrError(f"That address answered, but it doesn't look like {app}")
    return data


def root_folders(url, api_key, app="Radarr"):
    """Return the folder paths the app stores media in, as the server sees them."""
    return [folder["path"] for folder in call(url, api_key, "rootfolder", app)]


def movies(url, api_key):
    """Return every movie Radarr knows about.

    Each movie includes its folder (`path`) and, if Radarr has one, the file
    it tracks (`movieFile`) with quality and media details.
    """
    return call(url, api_key, "movie", "Radarr")


def series(url, api_key):
    """Return every TV show Sonarr knows about, each with its folder (`path`)."""
    return call(url, api_key, "series", "Sonarr")


def episode_files(url, api_key, series_id):
    """Return the episode files Sonarr tracks for one show, with quality details."""
    return call(url, api_key, f"episodefile?seriesId={int(series_id)}", "Sonarr")


# The command each app uses to re-read its library folders from disk.
RESCAN_COMMANDS = {"Radarr": "RescanMovie", "Sonarr": "RescanSeries"}


def rescan(url, api_key, app):
    """Ask Radarr or Sonarr to rescan all its folders. Returns the queued job's id."""
    job = call(url, api_key, "command", app, body={"name": RESCAN_COMMANDS[app]})
    return job.get("id") if isinstance(job, dict) else None
