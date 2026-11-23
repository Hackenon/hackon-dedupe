"""Where the app's files live — correct whether run from source or PyInstaller-frozen.

Two kinds of files:
  bundled()    read-only resources shipped with the app (templates, assets, docs).
  user_data()  files the app reads and writes (settings, results, logs, the ffprobe
               download, ...).

Running from source, both resolve next to the code, so development is unchanged.
In a packaged (frozen) build, bundled files come from the extracted bundle and user
data moves to a writable per-user folder (%APPDATA%\\HackOn on Windows), so the app
keeps working even when installed in a read-only location.
"""
import os
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)


def _resource_root():
    if FROZEN:
        # PyInstaller extracts bundled data here (the _internal dir for a onedir build).
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def bundled(*parts):
    """A read-only resource shipped with the app, e.g. bundled('assets')."""
    return _resource_root().joinpath(*parts)


def user_dir():
    """The writable folder for the app's own data (created if missing).

    From source: the project folder, so development is unchanged.
    Packaged: a per-user data folder outside the (possibly read-only) install location.
    """
    if not FROZEN:
        return Path(__file__).resolve().parent
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    folder = Path(base) / "HackOn"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def user_data(*parts):
    """A file or folder the app reads/writes, under user_dir()."""
    return user_dir().joinpath(*parts)
