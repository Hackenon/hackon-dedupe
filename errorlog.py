# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Log unexpected errors and turn them into bug reports.

Every unexpected error (a failed scan, or a page or button that crashes) is
written to logs/error-<time>-<id>.txt with the real technical details. API
keys and tokens are never written, even locally.

A bug report is that log with more removed: network addresses become <IP-1>,
<IP-2>..., and your Windows username becomes <user>. You see exactly what
would be sent, and you submit it yourself on GitHub. Nothing is sent
automatically.
"""

import getpass
import os
import platform
import re
import sys
import traceback
import urllib.parse
import uuid
from datetime import datetime
from pathlib import Path
import paths

APP_FOLDER = Path(__file__).parent
LOG_FOLDER = paths.user_data("logs")

# Where bug reports go if no repository is set in SETUP. Set this before release.
DEFAULT_REPO = "Hackenon/hackon-dedupe"  # confirmed public repo for bug reports (create the repo before release)

IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")


# ------------------------------------------------------------ writing logs

def app_version():
    """The current Git checkpoint (e.g. '9b258fb'), if the app is in a Git folder."""
    try:
        head = (APP_FOLDER / ".git" / "HEAD").read_text().strip()
        if head.startswith("ref: "):
            ref = head[5:]
            ref_file = APP_FOLDER / ".git" / ref
            if ref_file.exists():
                return ref_file.read_text().strip()[:7]
            packed = (APP_FOLDER / ".git" / "packed-refs").read_text()
            for line in packed.splitlines():
                if line.endswith(" " + ref):
                    return line[:7]
        return head[:7]
    except OSError:
        return "unknown"


def secrets_in(settings):
    """Every API key and token in the settings, so they can be removed from logs."""
    found = []
    for value in settings.values():
        if isinstance(value, dict):
            for key in ("api_key", "token", "client_id"):
                if value.get(key):
                    found.append(value[key])
    return found


def remove_secrets(text, settings):
    for secret in secrets_in(settings):
        text = text.replace(secret, "<secret>")
    return text


def settings_summary(settings):
    """Which features are set up, without any addresses or keys."""
    lines = []
    for service in ("radarr", "sonarr"):
        config = settings.get(service, {})
        mapped = sum(1 for v in config.get("path_map", {}).values() if v)
        lines.append(f"{service}: {'connected' if config.get('url') and config.get('api_key') else 'not set up'}, "
                     f"{mapped} folder(s) mapped")
    plex = settings.get("plex", {})
    lines.append(f"plex: {'signed in' if plex.get('token') else 'not signed in'}, "
                 f"rescan after move: {plex.get('rescan_after_move')}")
    lines.append(f"video details: {settings.get('media_details')}")
    return lines


def current_settings():
    """Settings for redaction. Imported here to avoid a circular import."""
    try:
        from settings import load_settings
        return load_settings()
    except Exception:
        return {}


def record_error(where, error, settings=None, recent_log=None, details=None):
    """Write an error log and return its id (e.g. '20261121-093412-4f2a').

    `error` is an exception; or pass `details` (text) for errors from the browser.
    """
    settings = settings if settings is not None else current_settings()
    problem = (f"Problem:  {type(error).__name__}: {error}" if isinstance(error, BaseException)
               else f"Problem:  {error}")
    repeat = same_unreviewed_error(f"Where:    {where}", problem)
    if repeat:  # the same thing again: note it on the existing log instead of a new one
        lines = repeat.read_text(encoding="utf-8").splitlines()
        lines.insert(2, f"Again:    {datetime.now():%Y-%m-%d %H:%M:%S}")
        repeat.write_text("\n".join(lines), encoding="utf-8")
        return repeat.stem[len("error-"):]
    error_id = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"
    if details is None:
        details = traceback.format_exception(type(error), error, error.__traceback__)
    lines = [
        f"ERROR {error_id}",
        f"When:     {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Where:    {where}",
        problem,
        "",
        f"App:      HackOn Photo & Video DeDupe, checkpoint {app_version()}",
        f"Python:   {platform.python_version()} ({sys.executable})",
        f"System:   {platform.platform()}",
        "",
        "Settings:",
        *("  " + line for line in settings_summary(settings)),
        "",
        "What the app was doing (last lines):",
        *("  " + line for line in (recent_log or [])[-25:]),
        "",
        "Technical details (traceback):",
        "".join(details).rstrip(),
    ]
    LOG_FOLDER.mkdir(exist_ok=True)
    text = remove_secrets("\n".join(lines), settings)
    (LOG_FOLDER / f"error-{error_id}.txt").write_text(text, encoding="utf-8")
    return error_id


# ------------------------------------------------------------ reading logs

def same_unreviewed_error(where_line, problem_line):
    """An unreviewed log of the same problem in the same place, or None."""
    for error_id in unreviewed_errors():
        path = LOG_FOLDER / f"error-{error_id}.txt"
        head = path.read_text(encoding="utf-8").splitlines()[:12]
        if where_line in head and problem_line in head:
            return path
    return None


def log_path(error_id):
    """The log file for an id, or None. Ids are checked so no other file can be read."""
    if not re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{4}", error_id or ""):
        return None
    path = LOG_FOLDER / f"error-{error_id}.txt"
    return path if path.exists() else None


def mark_reviewed(error_id):
    """Remember that you've seen this error's report page (stops the banner)."""
    path = log_path(error_id)
    if path:
        path.with_suffix(".reviewed").touch()


def mark_unreviewed(error_id):
    """Undo a dismiss: the error is reported in the banner again."""
    path = log_path(error_id)
    if path:
        path.with_suffix(".reviewed").unlink(missing_ok=True)


def unreviewed_errors():
    """Ids of logged errors you haven't looked at yet, newest first."""
    if not LOG_FOLDER.exists():
        return []
    return [path.stem[len("error-"):] for path in sorted(LOG_FOLDER.glob("error-*.txt"), reverse=True)
            if not path.with_suffix(".reviewed").exists()]


def all_errors():
    """Every error log, newest first, as dicts for the Errors page:
    id, when, where, problem, times (how often it happened), open (not dismissed)."""
    if not LOG_FOLDER.exists():
        return []
    found = []
    for path in sorted(LOG_FOLDER.glob("error-*.txt"), reverse=True):
        fields, times = {}, 1
        for line in path.read_text(encoding="utf-8").splitlines()[:40]:
            name, _, value = line.partition(":")
            if name in ("When", "Where", "Problem") and name.lower() not in fields:
                fields[name.lower()] = value.strip()
            elif name == "Again":
                times += 1
        found.append({"id": path.stem[len("error-"):], "times": times,
                      "open": not path.with_suffix(".reviewed").exists(),
                      "when": "", "where": "", "problem": "", **fields})
    return found


def has_errors():
    return LOG_FOLDER.exists() and any(LOG_FOLDER.glob("error-*.txt"))


def recent_errors(limit=10):
    """The newest error logs: [(id, first 'Problem:' line)]."""
    if not LOG_FOLDER.exists():
        return []
    found = []
    for path in sorted(LOG_FOLDER.glob("error-*.txt"), reverse=True)[:limit]:
        problem = next((line[10:] for line in path.read_text(encoding="utf-8").splitlines()
                        if line.startswith("Problem:")), "")
        found.append((path.stem[len("error-"):], problem))
    return found


# ------------------------------------------------------------ bug reports

def redact(text, settings):
    """Remove secrets, network addresses and your Windows username."""
    text = remove_secrets(text, settings)
    numbers = {}
    text = IPV4.sub(lambda m: numbers.setdefault(m.group(0), f"<IP-{len(numbers) + 1}>"), text)
    names = {getpass.getuser(), os.environ.get("USERNAME", ""), Path.home().name}
    for name in sorted((n for n in names if n and len(n) > 1), key=len, reverse=True):
        text = re.sub(rf"(?<![\w]){re.escape(name)}(?![\w])", "<user>", text, flags=re.IGNORECASE)
    return text


def bug_report(error_id, settings):
    """(title, body) for a GitHub issue, already redacted. None if the log doesn't exist."""
    path = log_path(error_id)
    if path is None:
        return None
    text = redact(path.read_text(encoding="utf-8"), settings)
    problem = next((line[10:] for line in text.splitlines() if line.startswith("Problem:")), "Unexpected error")
    where = next((line[10:] for line in text.splitlines() if line.startswith("Where:")), "")
    title = f"Bug: {problem[:90]}" + (f" ({where})" if where else "")
    body = (
        "**What happened**\n<!-- What were you doing when this happened? -->\n\n"
        f"**Error log** (`{error_id}`, network addresses and username removed)\n\n"
        f"```\n{text}\n```\n"
    )
    return title, body


def github_issue_url(repo, title, body):
    """A link that opens GitHub's 'new issue' page already filled in.

    GitHub can't take very long links, so if the report is too long the link
    carries a shortened copy, and the page offers the full text to paste.
    """
    base = f"https://github.com/{repo}/issues/new?"
    query = {"title": title, "body": body, "labels": "bug"}
    url = base + urllib.parse.urlencode(query)
    if len(url) > 7500:
        short = body[:3000] + "\n...\n```\n\n_(Report shortened: please paste the full report from the app below.)_\n"
        url = base + urllib.parse.urlencode({**query, "body": short})
    return url
