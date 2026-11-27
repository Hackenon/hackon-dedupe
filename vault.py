# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Keep API keys and the Plex token in the computer's own password store
(Windows Credential Manager, the Mac Keychain), not in settings.json.

Uses the `keyring` package. If it isn't installed, or the computer has no
password store, secrets stay in settings.json as before and Setup says so.
"""

import sys

try:
    import keyring
    from keyring.errors import KeyringError
except ImportError:  # not installed: fall back to settings.json
    keyring = None
    KeyringError = Exception

SERVICE = "hackon-dedupe"  # how the entries are labelled in the password store


def available():
    """True when there's a real password store to use."""
    if keyring is None:
        return False
    try:
        backend = keyring.get_keyring()
        # keyring's stand-in backends (no real store) have a priority of 0 or less.
        return float(backend.priority) > 0
    except Exception:
        return False


def store_name():
    """What to call the password store on the Setup page."""
    if sys.platform == "win32":
        return "WINDOWS CREDENTIAL MANAGER"
    if sys.platform == "darwin":
        return "MAC KEYCHAIN"
    return "SYSTEM KEYRING"


def get(name):
    """The saved secret, or "" if there isn't one."""
    return keyring.get_password(SERVICE, name) or ""


def _clear(name):
    """Remove every stored copy of a secret.

    Some password stores (notably Windows Credential Manager via keyring) leave
    a secret under two target names if it is written more than once. Each delete
    removes one copy, so loop until there is nothing left (bounded, so a backend
    that never signals "empty" can't loop forever)."""
    for _ in range(8):
        try:
            keyring.delete_password(SERVICE, name)
        except Exception:
            break  # nothing (more) stored under this name


def put(name, value):
    """Save a secret, or remove it when `value` is empty.

    Any existing copies are cleared first, so the store keeps exactly one entry
    per secret instead of accumulating duplicates when a secret is re-saved."""
    _clear(name)
    if value:
        keyring.set_password(SERVICE, name, value)
