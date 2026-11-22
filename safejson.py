"""Read and write the app's JSON data files safely.

If a file is empty, garbled, or has the wrong shape (for example after being
edited by hand), it is renamed to `name.broken-<date-time>.json` instead of
crashing the app, and the app carries on as if the file didn't exist. Nothing
is deleted, so anything useful in it can still be recovered.

Saving writes to a temporary file first and then swaps it in, so a crash in
the middle of saving can't leave a half-written file behind.
"""

import json
import os
from datetime import datetime

# Messages about files that were set aside, for the web app to show once.
notices = []


def read_json(path, default, valid=lambda data: True):
    """Return the data in `path`, or default() if it's missing or broken.

    `valid` is a function that checks the data has the expected shape.
    """
    if not path.exists():
        return default()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if valid(data):
            return data
        problem = "its contents weren't what the app expected"
    except UnicodeDecodeError:
        problem = "it isn't readable text"
    except json.JSONDecodeError:
        problem = "it's empty or isn't valid JSON"
    except OSError as error:
        problem = f"it couldn't be read ({error})"
    set_aside(path, problem)
    return default()


def set_aside(path, problem):
    """Rename a broken file out of the way and remember a message about it."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    broken = path.with_name(f"{path.stem}.broken-{stamp}{path.suffix}")
    try:
        path.rename(broken)
        where = f"It was renamed to {broken.name}."
    except OSError:
        where = "It couldn't be renamed, so it was ignored."
    notices.append(f"{path.name} was set aside because {problem}. {where}")


def write_json(path, data, indent=2):
    """Save `data` to `path` without ever leaving a half-written file."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=indent), encoding="utf-8")
    os.replace(temporary, path)  # swaps the new file in, in one step


def take_notices():
    """Return and clear the messages waiting to be shown."""
    waiting = notices[:]
    notices.clear()
    return waiting
