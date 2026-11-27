# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""The apps HackOn can integrate with, and the two roles they fill.

This is the single source of truth for provider support. The setup screen's
type pickers, the network-discovery probe, the settings schema, and the
dispatch layer all read from here, so adding support for a new app is mostly a
matter of adding an entry below (and its implementation).

Two roles:

  * media_server  -- rescans its library after a move, and is told to ignore
                     the `_review` folder. One per setup. Today: Plex.
  * movies / tv   -- the *library manager* that says authoritatively which file
                     on disk is the real copy to keep. Today: Radarr / Sonarr.

A provider is `available` (fully implemented and testable today) or `planned`
(known and discoverable, support not built yet). The picker offers available
providers for selection and shows planned ones as "coming soon"; discovery
reports a planned app as found-but-not-yet-supported rather than pretending it
can be configured.
"""

# ------------------------------------------------------------------- roles

ROLES = {
    "media_server": {
        "name": "Media server",
        "blurb": "Rescans its library after a move and hides the _review folder.",
        "single": True,          # at most one media server
        "auth": "varies",        # Plex uses PIN sign-in; others use an API key
    },
    "movies": {
        "name": "Movie library manager",
        "blurb": "Says which movie file is the real copy to keep.",
        "single": True,
        "auth": "api_key",
    },
    "tv": {
        "name": "TV library manager",
        "blurb": "Says which episode file is the real copy to keep.",
        "single": True,
        "auth": "api_key",
    },
}

# ------------------------------------------------------------- providers

# status: "available" = built and testable now; "planned" = discoverable, not built yet.
# auth:   "pin" = Plex-style PIN sign-in (token); "api_key" = X-Api-Key / api_key.
# kind:   groups providers that share an API dialect, used by the dispatch layer.
# port:   default port, used by network discovery.
PROVIDERS = {
    # media server
    "plex": {
        "role": "media_server", "name": "Plex", "port": 32400,
        "status": "available", "auth": "pin", "kind": "plex",
    },
    "jellyfin": {
        "role": "media_server", "name": "Jellyfin", "port": 8096,
        "status": "available", "auth": "api_key", "kind": "jellyfin",
    },
    "emby": {
        "role": "media_server", "name": "Emby", "port": 8096,
        "status": "planned", "auth": "api_key", "kind": "emby",
    },
    # movie library manager
    "radarr": {
        "role": "movies", "name": "Radarr", "port": 7878,
        "status": "available", "auth": "api_key", "kind": "arr",
    },
    # TV library manager
    "sonarr": {
        "role": "tv", "name": "Sonarr", "port": 8989,
        "status": "available", "auth": "api_key", "kind": "arr",
    },
    "medusa": {
        "role": "tv", "name": "Medusa", "port": 8081,
        "status": "planned", "auth": "api_key", "kind": "medusa",
    },
    "sickgear": {
        "role": "tv", "name": "SickGear", "port": 8081,
        "status": "planned", "auth": "api_key", "kind": "medusa",
    },
}


# --------------------------------------------------------------- helpers

def get(key):
    """The provider record for `key`, or None."""
    return PROVIDERS.get(key)


def exists(key):
    return key in PROVIDERS


def is_available(key):
    return PROVIDERS.get(key, {}).get("status") == "available"


def role_of(key):
    return PROVIDERS.get(key, {}).get("role")


def secret_field(key):
    """The settings field that holds this provider's secret ('token' or 'api_key')."""
    return "token" if PROVIDERS.get(key, {}).get("auth") == "pin" else "api_key"


def for_role(role, status=None):
    """Provider keys for a role, in registry order. Optionally filter by status."""
    return [k for k, p in PROVIDERS.items()
            if p["role"] == role and (status is None or p["status"] == status)]


def available_for(role):
    return for_role(role, "available")


def planned_for(role):
    return for_role(role, "planned")


def options_for(role):
    """Picker options for a role: [{key, name, status, port, auth}], available first."""
    out = []
    for status in ("available", "planned"):
        for key in for_role(role, status):
            p = PROVIDERS[key]
            out.append({"key": key, "name": p["name"], "status": status,
                        "port": p["port"], "auth": p["auth"]})
    return out


def discovery_targets():
    """What network discovery should probe: one entry per (name, port), with
    the lowest-status providers folded in. Available apps first.

    Returns [{"keys": [...], "name": ..., "port": ..., "kind": ..., "status": ...}].
    Providers that share a port (Jellyfin/Emby on 8096, Medusa/SickGear on 8081)
    are reported together, since a bare port can't tell them apart.
    """
    by_port = {}
    for key, p in PROVIDERS.items():
        slot = by_port.setdefault(p["port"], {
            "keys": [], "names": [], "port": p["port"],
            "kind": p["kind"], "status": p["status"],
        })
        slot["keys"].append(key)
        slot["names"].append(p["name"])
        # a port is "available" if any provider on it is available
        if p["status"] == "available":
            slot["status"] = "available"
    targets = []
    for port, slot in by_port.items():
        targets.append({
            "keys": slot["keys"],
            "name": " / ".join(slot["names"]),
            "port": port,
            "kind": slot["kind"] if len(slot["keys"]) == 1 else "shared",
            "status": slot["status"],
        })
    return sorted(targets, key=lambda t: (t["status"] != "available", t["port"]))
