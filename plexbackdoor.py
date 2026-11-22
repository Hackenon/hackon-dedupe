"""The Plex "backdoor": use Plex without signing in, when Plex already trusts
this network.

Plex has a setting (Settings > Network > "List of IP addresses and networks
that are allowed without auth"). When this computer's network is on that list,
Plex answers without a token. This module only DETECTS that; it never changes
Plex's settings.

Removable: set ENABLED = False to switch it off everywhere (the Setup row
disappears and the app goes back to needing the PIN sign-in). To remove it
completely, delete this file and the lines marked "# backdoor" in app.py and
setup.html. A leftover "backdoor" value in settings.json is then ignored.
"""

import plex

ENABLED = True


def is_open(settings):
    """True when the last probe found the backdoor open (and the feature is on)."""
    return ENABLED and bool(settings["plex"].get("backdoor"))


def probe(url, client_id):
    """Knock on Plex without a token. Returns True if it lets us in, False if
    it asks for a sign-in. Raises plex.PlexError if Plex can't be reached."""
    try:
        plex.libraries(url, client_id, None)
        return True
    except plex.PlexAuthError:
        return False
