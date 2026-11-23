"""HackOn Photo & Video DeDupe web app.

Run with:  python app.py
Then open: http://127.0.0.1:5000
"""

import io
import mimetypes
import ctypes
import logging
from urllib.parse import urlsplit
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import paths

from flask import (Flask, abort, flash, jsonify, redirect, render_template, request,
                   send_file, send_from_directory, session, url_for)
from werkzeug.exceptions import HTTPException

import errorlog
import tracer
from PIL import Image, ImageOps
try:  # optional .HEIC/.HEIF support (iPhone photos) when pillow-heif is installed
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

import arr
import arrkey  # apikey
import netscan  # netscan
import helpdocs
import plex
import plexbackdoor  # backdoor
import vault
from mediatools import folder_contents, folder_key, video_files
from netpaths import network_host, network_prefix, swap_host, to_server_path, translate
from mover import files_to_move, load_moves, move_extras, undo_last
import mediamover
from moviescan import load_movie_results, run_movie_scan, save_movie_results
from tvscan import load_tv_results, run_tv_scan, save_tv_results
from folderscan import run_folder_scan
from mediadetails import add_details, count_needing_details, ffprobe_path
from cache import FingerprintCache
from results import load_results, run_scan, save_results
import reviewcleanup
import playback
import ffmpegsetup
from near import UNREADABLE
from scan import VIDEO_TYPES, folder_has_media
from safejson import read_json, take_notices, write_json
from settings import (SERVICES, is_configured, load_settings, mask, plex_client_id,
                      save_settings)

app = Flask(__name__, template_folder=str(paths.bundled("templates")))
ASSETS_FOLDER = paths.bundled("assets")


@app.route("/assets/<path:name>")
def asset(name):
    """Serve the logo / icon files from the assets folder."""
    return send_from_directory(ASSETS_FOLDER, name)
app.secret_key = os.urandom(16)  # needed for flash() messages

# ---------------------------------------------------------------- only this computer
# The app listens on 127.0.0.1, but a web page open in the same browser could
# still try to use it. Two checks stop that:
#  1. The address must be this computer's own name. A trick called DNS
#     rebinding makes an outside website's name point at 127.0.0.1 so it can
#     read the app's pages; its requests still carry that website's name.
#  2. Anything that changes something (POST) must come from the app's own
#     pages. Browsers label every request with the page it came from (Origin).
#     Requests with no label don't come from a web page (e.g. Python tools).

LOCAL_NAMES = {"127.0.0.1", "localhost", "[::1]"}


@app.before_request
def only_this_computer():
    host = request.host.lower()
    name = host.split("]")[0] + "]" if host.startswith("[") else host.rsplit(":", 1)[0]
    if name not in LOCAL_NAMES:
        abort(403, "This app only answers to 127.0.0.1")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        source = request.headers.get("Origin") or request.headers.get("Referer")
        if source and urlsplit(source).netloc.lower() != host:
            abort(403, "Blocked: another website tried to use this app")

THUMB_SIZE = (320, 320)

# Folder shortcuts are saved in settings.json (see settings.py), with everything else.

# The order sections appear on the page, and their headings.
SECTIONS = {
    "exact": "Exact duplicates",
    "copy": "Copies",
    "similar": "Similar shots",
}


def get_file(results, group_id, index):
    """Return the entry for file `index` in group `group_id`.

    The browser only ever sends numbers, never file paths, so a web page
    can't ask for files outside the scan.
    """
    for group in results["groups"]:
        if group["id"] == group_id and 0 <= index < len(group["files"]):
            return group["files"][index]
    abort(404)


def get_path(results, group_id, index):
    """Return where file `index` in group `group_id` is now on disk."""
    file = get_file(results, group_id, index)
    return Path(results["folder"]) / file.get("moved_to", file["path"])


def media_disk_path(results, group_id, index):
    """Where file `index` of group `group_id` lives now, for media results.

    Media moves record an absolute `moved_to`; otherwise the file sits in the
    group's folder under its own name. Looked up by id + index, so the browser
    can only ever reach a file the last scan already found.
    """
    for group in results["groups"]:
        if group["id"] == group_id and 0 <= index < len(group["files"]):
            file = group["files"][index]
            if file.get("moved_to"):
                return Path(file["moved_to"])
            return Path(group["folder"]) / file["name"]
    abort(404)


def stray_disk_path(results, index):
    """The video to play for stray `index`: the loose file itself, or the
    largest video inside a stray folder. Reached by index, never by a path
    from the browser.
    """
    strays = results.get("strays", []) if results else []
    if not (0 <= index < len(strays)):
        abort(404)
    stray = strays[index]
    if stray.get("kind") == "empty folder":
        abort(404)
    path = Path(stray["path"])
    if path.is_file():
        return path
    if path.is_dir():
        videos = video_files(path)
        if videos:
            return max(videos, key=lambda p: p.stat().st_size)
    abort(404)


def stray_registry_path(results, index):
    """What the unplayable memory is keyed on for a stray: its own path (cheap
    to check at render), not the inner video we happen to stream."""
    strays = results.get("strays", []) if results else []
    if not (0 <= index < len(strays)):
        abort(404)
    return Path(strays[index]["path"])


@app.context_processor
def menu_state():
    """Values every page needs: whether Plex is signed in (for the Plex
    buttons), and messages about data files that were broken and set aside.
    """
    settings = load_settings()
    return {
        "plex_ready": plex_signed_in(settings),
        "backdoor_open": plexbackdoor.is_open(settings),  # backdoor
        "file_notices": take_notices(),
        "unreviewed_errors": errorlog.unreviewed_errors(),
        "has_errors": errorlog.has_errors(),
    }


@app.template_filter("size")
def format_size(num_bytes):
    """1536000000 -> '1.5 GB' for the pages."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1000:
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1000
    return f"{num_bytes:.2f} TB"


@lru_cache(maxsize=2000)
def make_thumbnail(path_string, modified_time):
    """Return a small JPEG of a photo as bytes. Results are remembered
    (cached), so each thumbnail is only built once."""
    with Image.open(path_string) as img:
        img.draft("RGB", THUMB_SIZE)
        img = ImageOps.exif_transpose(img)
        img.thumbnail(THUMB_SIZE)
        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, "JPEG", quality=80)
    return buffer.getvalue()


# ---------------------------------------------------------------- start page

def load_shortcuts():
    return load_settings()["shortcuts"]


def save_shortcuts(shortcuts):
    settings = load_settings()
    settings["shortcuts"] = shortcuts
    save_settings(settings)


@app.before_request
def first_run():
    """When the app first opens and setup isn't done, show the setup screen
    once. After that, Photo Scan works freely (it doesn't need any setup),
    so clicking it never bounces back here."""
    if (request.endpoint == "start" and not load_settings()["setup_done"]
            and not session.get("saw_setup")):
        return redirect(url_for("setup"))


def photo_results_context():
    """Everything the photo results section needs, or {} if there's no scan yet."""
    results = load_results()
    if results is None:
        return {}
    for group in results["groups"]:
        for file in group["files"]:
            file["is_video"] = Path(file["path"]).suffix.lower() in VIDEO_TYPES
    kinds = [group["kind"] for group in results["groups"]]
    return {
        "results": results,
        "result_sections": [
            (title, [g for g in results["groups"] if g["kind"] == kind])
            for kind, title in SECTIONS.items()
        ],
        "to_move": len(list(files_to_move(results))),
        "can_undo": bool(load_moves()),
        "empty_folders": results.get("empty_folders", []),
        "summary": {
            "folder": results["folder"],
            "scanned_at": results["scanned_at"].replace("T", " "),
            "counts": results["counts"],
            "groups": {kind: kinds.count(kind) for kind in SECTIONS},
        },
    }


_cleanup_done = False


def ensure_review_cleanup():
    """Once per app load, forget files the user deleted out of _review.

    Runs the first time a page is viewed (so it happens in the worker process,
    not the auto-reloader's parent) and never blocks the page: any trouble is
    logged as a normal error, not shown to the user.
    """
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True
    try:
        reviewcleanup.clean_all(load_settings())
    except Exception as error:  # cleanup must never stop the app from loading
        errorlog.record_error("cleaning up deleted review files", error)


@app.route("/")
def start():
    """PHOTO SCAN: choose a folder, scan it, and review the results below."""
    ensure_review_cleanup()
    return render_template("start.html", shortcuts=load_shortcuts(), sections=SECTIONS,
                           plex_photos=plex_photo_folders(load_settings()),
                           scanned=load_results() is not None,
                           **photo_results_context())


@app.post("/shortcuts")
def add_shortcut():
    path = (request.json or {}).get("path", "").strip()
    if not path or not Path(path).is_dir():
        return {"error": "Not a folder"}, 400
    shortcuts = load_shortcuts()
    if path not in [s["path"] for s in shortcuts]:
        shortcuts.append({"name": Path(path).name or path, "path": path})
        save_shortcuts(shortcuts)
    return {"ok": True}


@app.post("/shortcuts/<int:index>/delete")
def delete_shortcut(index):
    shortcuts = load_shortcuts()
    if 0 <= index < len(shortcuts):
        shortcuts.pop(index)
        save_shortcuts(shortcuts)
    return {"ok": True}


# The Windows folder picker runs as its own small Python program, so it
# can't interfere with the web server. It prints the chosen folder.
PICKER_PROGRAM = """
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)   # open in front of the browser
print(filedialog.askdirectory(title="Choose a folder to scan") or "", end="")
"""


@app.post("/browse")
def browse():
    try:
        result = subprocess.run([sys.executable, "-c", PICKER_PROGRAM],
                                capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return {"error": "The folder picker was open too long; try again"}, 400
    if result.returncode != 0:
        lines = result.stderr.strip().splitlines() or ["Folder picker failed"]
        error_id = errorlog.record_error("folder picker (BROWSE)", lines[-1],
                                         details=result.stderr or "(no output)")
        return {"error": lines[-1], "error_id": error_id}, 500
    chosen = result.stdout.strip()
    return {"path": str(Path(chosen)) if chosen else None}


# ---------------------------------------------------------------- setup screen
# Radarr and Sonarr are set up the same way: address, API key, root folders
# and how this computer reaches them. Saved to settings.json. API keys are
# never sent back to the browser.

@app.route("/help")
def help_page():
    """The in-app Help & Install guide (rendered from docs/)."""
    return render_template("help.html",
                           help_html=helpdocs.load("HELP.md"),
                           install_html=helpdocs.load("INSTALL.md"),
                           help_toc=helpdocs.contents("HELP.md"),
                           install_toc=helpdocs.contents("INSTALL.md"))


@app.route("/setup")
def setup():
    settings = load_settings()
    services = [
        {
            "key": service,
            **details,
            "url": settings[service]["url"],
            "key_hint": mask(settings[service]["api_key"]),
            "path_map": settings[service]["path_map"],
            "move_to": settings[service].get("move_to", ""),
        }
        for service, details in SERVICES.items()
    ]
    plex_settings = settings["plex"]
    session["saw_setup"] = True  # don't force Photo Scan back here again
    return render_template(
        "setup.html",
        help_toc=helpdocs.contents("HELP.md"),
        services=services,
        plex={
            "url": plex_settings["url"],
            "signed_in": bool(plex_settings["token"]),
            "backdoor": plexbackdoor.is_open(settings),  # backdoor
            "path_map": plex_settings["path_map"],
            "rescan_after_move": plex_settings["rescan_after_move"],
        },
        first_run=not settings["setup_done"],
        network_prefix=network_prefix(),
        backdoor_enabled=plexbackdoor.ENABLED,  # backdoor
        apikey_enabled=arrkey.ENABLED,  # apikey
        netscan_enabled=netscan.ENABLED,  # netscan
        key_store=vault.store_name() if vault.available() else None,
        media_details=settings["media_details"],
        has_ffprobe=bool(ffprobe_path()),
        can_get_ffmpeg=ffmpegsetup.can_download(),
        ffmpeg_size=ffmpegsetup.size_hint(),
        bug_report_repo=settings["bug_report_repo"],
        error_count=len(errorlog.all_errors()),
    )


def service_or_404(service):
    if service not in SERVICES:
        abort(404)
    return SERVICES[service]["name"]


def connection_details(service, form):
    """Return (url, api_key) from the page, using the saved key if the box was left blank."""
    url = arr.normalize_url(form.get("url", ""))
    api_key = form.get("api_key", "").strip() or load_settings()[service]["api_key"]
    return url, api_key


@app.post("/setup/probe-network")  # netscan
def setup_probe_network():
    """Scan this computer's own /24 for Radarr, Sonarr and Plex."""
    if not netscan.ENABLED:
        abort(404)
    result = netscan.scan()
    if "error" in result:
        return result, 400
    return result


@app.post("/setup/<service>/probe-key")  # apikey
def setup_probe_key(service):
    """Read the API key from Radarr/Sonarr when it trusts this network."""
    app_name = service_or_404(service)
    if not arrkey.ENABLED:
        abort(404)
    url = arr.normalize_url((request.json or {}).get("url", ""))
    if not url:
        return {"error": f"Enter {app_name}'s address first"}, 400
    try:
        key = arrkey.read_key(url, app_name)
    except arr.ArrError as error:
        return {"error": str(error)}, 400
    if not key:
        return {"found": False}, 200
    # Confirm the key actually works before handing it back.
    try:
        info = arr.status(url, key, app_name)
    except arr.ArrError:
        return {"found": False}, 200
    return {"found": True, "api_key": key, "version": info.get("version", "?")}


@app.post("/setup/<service>/test")
def setup_test(service):
    app_name = service_or_404(service)
    url, api_key = connection_details(service, request.json or {})
    try:
        info = arr.status(url, api_key, app_name)
        folders = arr.root_folders(url, api_key, app_name)
    except arr.ArrError as error:
        return {"error": str(error)}, 400
    # If the app runs on the same computer as Radarr/Sonarr (or they use a
    # network path like \\server\share), their own path works here as-is.
    return {
        "version": info.get("version", "?"),
        "root_folders": [
            {"path": folder, "reachable": reachable(folder), "host": network_host(folder)}
            for folder in folders
        ],
    }


def reachable(path):
    """True if this computer can open the folder."""
    return bool(path) and Path(path).is_dir()


@app.post("/setup/try-host")
def setup_try_host():
    """Try network paths with a different server address.

    For a NAS with two addresses: Radarr may use one that only the server can
    reach, while this computer needs the other.
    """
    form = request.json or {}
    new_host = form.get("host", "").strip()
    if not new_host:
        return {"error": "Enter an address"}, 400
    attempts = []
    for path in form.get("paths", []):
        suggestion = swap_host(path, new_host)
        attempts.append({"path": path, "suggestion": suggestion, "reachable": reachable(suggestion)})
    return {"attempts": attempts}


@app.post("/setup/check-path")
def setup_check_path():
    path = (request.json or {}).get("path", "").strip()
    return {"exists": reachable(path)}


@app.post("/setup/save")
def setup_save():
    """Save every service at once. A service left completely blank is fine."""
    form = (request.json or {}).get("services", {})
    settings = load_settings()
    key_hints = {}
    for service in SERVICES:
        page = form.get(service) or {}
        url, api_key = connection_details(service, page)
        settings[service] = {
            "url": url,
            "api_key": api_key,
            "path_map": {
                server_path: pc_path.strip()
                for server_path, pc_path in (page.get("path_map") or {}).items()
            },
            "move_to": str(((request.json or {}).get("move_to") or {}).get(service, "")).strip(),
        }
        key_hints[service] = mask(api_key)
    plex_page = (request.json or {}).get("plex") or {}
    settings["plex"].update({
        "url": plex.normalize_url(plex_page.get("url", "")),
        "path_map": {
            server_path: pc_path.strip()
            for server_path, pc_path in (plex_page.get("path_map") or {}).items()
        },
        "rescan_after_move": bool(plex_page.get("rescan_after_move", True)),
    })  # the token is never taken from the page; only sign-in sets it
    repo = str((request.json or {}).get("bug_report_repo", settings["bug_report_repo"])).strip().strip("/")
    if repo.startswith("https://github.com/"):
        repo = repo[len("https://github.com/"):]
    settings["bug_report_repo"] = repo
    if (request.json or {}).get("media_details") in ("button", "auto"):
        settings["media_details"] = request.json["media_details"]
    settings["setup_done"] = True
    save_settings(settings)
    return {"ok": True, "key_hints": key_hints}


# ---- Get ffprobe for the user (no winget/Homebrew; downloads an LGPL build) ----
ffmpeg_job = {"running": False, "log": [], "done": False, "error": None}


@app.post("/setup/get-ffmpeg")
def get_ffmpeg():
    """DOWNLOAD FFMPEG button: fetch an LGPL ffprobe into the app's bin folder."""
    if ffprobe_path():
        return {"ok": True, "message": "ffprobe is already available"}
    if not ffmpegsetup.can_download():
        return {"error": "Automatic download isn't available on this system yet. "
                         "Install FFmpeg yourself and it'll be found on PATH."}, 400
    if ffmpeg_job["running"]:
        return {"error": "A download is already running"}, 409

    def progress(message):
        ffmpeg_job["log"].append(message)

    def worker():
        try:
            ffmpegsetup.download(progress)
            ffmpeg_job["done"] = True
        except ffmpegsetup.FFmpegError as error:
            ffmpeg_job["error"] = str(error)          # expected problem, not a bug
        except Exception as error:                     # anything unexpected: log it
            ffmpeg_job["error"] = str(error)
            errorlog.record_error("downloading ffprobe", error, load_settings())
        finally:
            ffmpeg_job["running"] = False

    ffmpeg_job.update(running=True, log=[], done=False, error=None)
    threading.Thread(target=worker, daemon=True).start()
    return {"ok": True, "started": True, "size_hint": ffmpegsetup.size_hint()}


@app.route("/setup/get-ffmpeg/status")
def get_ffmpeg_status():
    since = request.args.get("since", 0, type=int)
    return {
        "lines": ffmpeg_job["log"][since:],
        "running": ffmpeg_job["running"],
        "done": ffmpeg_job["done"],
        "error": ffmpeg_job["error"],
        "has_ffprobe": bool(ffprobe_path()),
    }


# ---- Plex: PIN sign-in and connection test

@app.post("/setup/plex/signin")
def plex_signin_start():
    """Ask plex.tv for a PIN; the page opens Plex's approval page in a new tab."""
    try:
        pin_id, page = plex.start_pin(plex_client_id())
    except plex.PlexError as error:
        return {"error": str(error)}, 400
    return {"pin_id": pin_id, "page": page}


@app.route("/setup/plex/signin/<int:pin_id>")
def plex_signin_check(pin_id):
    """Called every few seconds by the page until you've approved the PIN."""
    try:
        token = plex.check_pin(plex_client_id(), pin_id)
    except plex.PlexError as error:
        return {"error": str(error)}, 400
    if not token:
        return {"signed_in": False}
    settings = load_settings()
    settings["plex"]["token"] = token  # saved straight away, never sent to the page
    save_settings(settings)
    return {"signed_in": True}


@app.post("/setup/plex/signout")
def plex_signout():
    settings = load_settings()
    settings["plex"]["token"] = ""
    save_settings(settings)
    return {"ok": True}


@app.post("/setup/plex/backdoor")  # backdoor
def plex_backdoor_probe():
    """Knock on Plex without a token and remember whether it let us in."""
    if not plexbackdoor.ENABLED:
        abort(404)
    url = plex.normalize_url((request.json or {}).get("url", ""))
    if not url:
        return {"error": "Enter your Plex server's address first"}, 400
    try:
        is_open = plexbackdoor.probe(url, plex_client_id())
    except plex.PlexError as error:
        return {"error": str(error)}, 400
    settings = load_settings()
    settings["plex"]["backdoor"] = is_open
    save_settings(settings)
    return {"open": is_open, "network": network_prefix()}


@app.post("/setup/plex/test")
def plex_test():
    settings = load_settings()
    url = plex.normalize_url((request.json or {}).get("url", ""))
    token = settings["plex"]["token"]
    if not token and not plexbackdoor.is_open(settings):  # backdoor: no token needed when open
        return {"error": "Sign in with Plex first"}, 400
    try:
        name, version = plex.server_info(url, plex_client_id(), token)
        found = plex.libraries(url, plex_client_id(), token)
    except plex.PlexError as error:
        return {"error": str(error)}, 400
    for library in found:
        library["folders"] = [
            {"path": folder, "reachable": reachable(folder), "host": network_host(folder)}
            for folder in library["folders"]
        ]
    return {"name": name, "version": version, "libraries": found}


@app.post("/setup/skip")
def setup_skip():
    settings = load_settings()
    settings["setup_done"] = True
    save_settings(settings)
    return {"ok": True}


# ---------------------------------------------------------------- scanning
# A scan can take minutes, so it runs in a background thread while the page
# asks for new log lines every half second.

scan_job = {"running": False, "log": [], "error": None, "error_id": None}


def run_in_background(work):
    """Run work(progress) in a background thread, collecting its log lines.

    Used by both the photo scan and the movie scan. Only one runs at a time.
    """
    def progress(message):
        scan_job["log"].append(f"{datetime.now():%H:%M:%S}  {message}")

    def worker():
        try:
            work(progress)
        except Exception as error:
            scan_job["error"] = str(error)
            progress(f"ERROR: {error}")
            try:
                scan_job["error_id"] = errorlog.record_error(
                    "background scan", error, load_settings(), recent_log=scan_job["log"])
            except Exception:
                pass  # never let logging hide the original problem
        finally:
            scan_job["running"] = False

    scan_job.update(running=True, log=[], error=None, error_id=None)
    threading.Thread(target=worker, daemon=True).start()


def photo_scan(folder, progress):
    save_results(run_scan(folder, progress))
    make_thumbnail.cache_clear()


@app.post("/scan")
def start_scan():
    folder = (request.json or {}).get("folder", "").strip()
    if scan_job["running"]:
        return {"error": "A scan is already running"}, 409
    if not folder or not Path(folder).is_dir():
        return {"error": f"Not a folder: {folder}"}, 400

    run_in_background(lambda progress: photo_scan(folder, progress))
    return {"ok": True}


@app.route("/scan/status")
def scan_status():
    since = request.args.get("since", 0, type=int)
    return {
        "lines": scan_job["log"][since:],
        "running": scan_job["running"],
        "error": scan_job["error"],
        "error_id": scan_job["error_id"],
    }


# ---------------------------------------------------------------- movies and TV
# Read-only: compares Radarr's movies / Sonarr's shows with their folders.
# Both use the same page (templates/media.html) with different wording.

# --------------------------------------------------------------- play a file
# PLAY button: stream a browser-playable file into the page frame; fall back to
# VLC's own window for anything the browser can't decode; if neither works,
# remember the file as unplayable so the button stays greyed. Files are reached
# by group id + index, never by a path from the browser.

def _play_target(kind, group_id, index):
    if kind not in MEDIA_PAGES:
        abort(404)
    results = MEDIA_PAGES[kind]["load"]()
    if results is None:
        abort(404)
    return media_disk_path(results, group_id, index)


@app.get("/<kind>/play/<int:group_id>/<int:index>")
def media_play_stream(kind, group_id, index):
    path = _play_target(kind, group_id, index)
    if not path.is_file():
        abort(404)
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return send_file(str(path), mimetype=mime, conditional=True)


@app.post("/<kind>/play-vlc/<int:group_id>/<int:index>")
def media_play_vlc(kind, group_id, index):
    path = _play_target(kind, group_id, index)
    if not path.is_file():
        return {"error": "File not found"}, 404
    return {"launched": playback.launch_vlc(path)}


@app.post("/<kind>/play-unplayable/<int:group_id>/<int:index>")
def media_play_unplayable(kind, group_id, index):
    playback.mark_unplayable(_play_target(kind, group_id, index))
    return {"ok": True}


def _stray_results(kind):
    if kind not in MEDIA_PAGES:
        abort(404)
    results = MEDIA_PAGES[kind]["load"]()
    if results is None:
        abort(404)
    return results


@app.get("/<kind>/play-stray/<int:index>")
def media_play_stray(kind, index):
    path = stray_disk_path(_stray_results(kind), index)
    if not path.is_file():
        abort(404)
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return send_file(str(path), mimetype=mime, conditional=True)


@app.post("/<kind>/play-stray-vlc/<int:index>")
def media_play_stray_vlc(kind, index):
    path = stray_disk_path(_stray_results(kind), index)
    if not path.is_file():
        return {"error": "File not found"}, 404
    return {"launched": playback.launch_vlc(path)}


@app.post("/<kind>/play-stray-unplayable/<int:index>")
def media_play_stray_unplayable(kind, index):
    playback.mark_unplayable(stray_registry_path(_stray_results(kind), index))
    return {"ok": True}


MEDIA_PAGES = {
    "movies": {
        "service": "radarr", "app": "Radarr", "heading": "MOVIES", "things": "movie",
        "one_thing": "movie", "group_label": "movies", "count_key": "movies",
        "scan_url": "/movies/scan", "load": load_movie_results, "save": save_movie_results,
        "about": "Radarr (free, radarr.video) manages a movie collection: it downloads, renames and "
                 "sorts movies, and knows exactly which file belongs to each movie. Connected here, this "
                 "app can tell the real copy from leftovers with certainty, find stray and empty folders "
                 "Radarr doesn't know about, and ask Radarr to rescan after a clean-up.",
        "scan": lambda settings, progress: save_movie_results(with_details(run_movie_scan(settings, progress), progress)),
    },
    "tv": {
        "service": "sonarr", "app": "Sonarr", "heading": "TV SHOWS", "things": "TV show",
        "one_thing": "episode", "group_label": "episodes", "count_key": "shows",
        "scan_url": "/tv/scan", "load": load_tv_results, "save": save_tv_results,
        "about": "Sonarr (free, sonarr.tv) manages TV shows: it downloads, renames and sorts episodes, "
                 "and knows exactly which file belongs to each episode. Connected here, this app can tell "
                 "the real copy from leftovers with certainty, find stray and empty folders Sonarr doesn't "
                 "know about, and ask Sonarr to rescan after a clean-up.",
        "scan": lambda settings, progress: save_tv_results(with_details(run_tv_scan(settings, progress), progress)),
    },
}


def with_details(results, progress):
    """In "automatic" mode, read missing video details right after a scan."""
    if load_settings()["media_details"] == "auto":
        if ffprobe_path():
            add_details(results, progress)
        else:
            progress("Skipped reading video details: ffprobe not found (install FFmpeg)")
    return results


@app.template_filter("browser_playable")
def _tpl_browser_playable(name):
    """Jinja: 1 when it's worth the browser trying this file in the frame."""
    return playback.browser_can_try(name)


def unplayable_stray_keys(results):
    """Indices of strays the browser AND VLC couldn't play. Empty when VLC is
    installed (it can play anything), so the strays page stays cheap to render.
    """
    keys = set()
    if not results or playback.vlc_available():
        return keys
    for i, stray in enumerate(results.get("strays", [])):
        if stray.get("kind") == "empty folder":
            continue
        if playback.is_unplayable(Path(stray["path"])):
            keys.add(i)
    return keys


def unplayable_keys(results):
    """"group:index" keys for files the browser AND VLC couldn't play.

    Only meaningful when VLC is missing: with VLC installed every file is
    playable in VLC's window, so nothing is greyed out.
    """
    keys = set()
    if not results or playback.vlc_available():
        return keys
    for group in results["groups"]:
        for i, file in enumerate(group["files"]):
            path = Path(file["moved_to"]) if file.get("moved_to") else Path(group["folder"]) / file["name"]
            if playback.is_unplayable(path):
                keys.add("%s:%s" % (group["id"], i))
    return keys


def media_page(kind):
    ensure_review_cleanup()
    page = MEDIA_PAGES[kind]
    settings = load_settings()
    configured = is_configured(settings, page["service"])
    results = page["load"]()
    _, plan = media_move_plan(kind, results, settings) if results else (results, [])
    return render_template("media.html", page=page, kind=kind, results=results, configured=configured,
                           needs_details=count_needing_details(results), has_ffprobe=bool(ffprobe_path()),
                           to_move=len(plan), tracked_to_move=mediamover.tracked_in(plan),
                           can_undo=bool(mediamover.load_moves(kind)),
                           move_default=settings[page["service"]].get("move_to", ""),
                           vlc_ready=playback.vlc_available(),
                           unplayable=unplayable_keys(results),
                           unplayable_strays=unplayable_stray_keys(results))


@app.post("/<kind>/details")
def read_details(kind):
    """GET DETAILS button: fill in resolution, codec and length with ffprobe."""
    if kind not in MEDIA_PAGES:
        abort(404)
    if scan_job["running"]:
        return {"error": "A scan is already running"}, 409
    if not ffprobe_path():
        return {"error": "ffprobe not found. Use GET FFMPEG in Setup to add it."}, 400
    page = MEDIA_PAGES[kind]
    if page["load"]() is None:
        return {"error": "Scan first"}, 400

    def work(progress):
        results = page["load"]()
        add_details(results, progress)
        page["save"](results)

    run_in_background(work)
    return {"ok": True}


def start_media_scan(kind):
    page = MEDIA_PAGES[kind]
    if scan_job["running"]:
        return {"error": "A scan is already running"}, 409
    settings = load_settings()
    if not is_configured(settings, page["service"]):
        return {"error": f"Connect {page['app']} and map its folders in SETUP first"}, 400
    run_in_background(lambda progress: page["scan"](settings, progress))
    return {"ok": True}


# ------------------------------------------------- removing empty stray folders
# "Empty" means no video files; posters, subtitles or .nfo files may remain.
# Only folders listed by the last scan are ever deleted, each one re-checked
# for video right before deleting. Deleting is permanent (no undo).

def empty_stray_folders(kind):
    """Empty stray folders from the last scan that are still safe to delete."""
    page = MEDIA_PAGES[kind]
    results = page["load"]()
    settings = load_settings()
    roots = {folder_key(local) for local in settings[page["service"]]["path_map"].values() if local}
    folders = []
    for stray in (results or {}).get("strays", []):
        if stray.get("kind") != "empty folder":
            continue
        path = Path(stray["path"])
        # Must still exist, and sit directly inside one of the mapped root folders.
        if not path.is_dir() or folder_key(path.parent) not in roots:
            continue
        folders.append({"name": stray["name"], "path": str(path), **folder_contents(path)})
    return folders


@app.route("/<kind>/empty-folders")
def list_empty_folders(kind):
    if kind not in MEDIA_PAGES:
        abort(404)
    folders = [f for f in empty_stray_folders(kind) if not f["has_video"]]
    return {"folders": folders}


@app.post("/<kind>/empty-folders/delete")
def delete_empty_folders(kind):
    if kind not in MEDIA_PAGES:
        abort(404)
    wanted = set((request.json or {}).get("paths", []))
    allowed = {f["path"]: f for f in empty_stray_folders(kind)}
    deleted, skipped = [], []
    for path in wanted:
        folder = allowed.get(path)
        if folder is None:
            skipped.append({"path": path, "reason": "not in the scan's list of empty folders"})
            continue
        if folder_contents(path)["has_video"]:  # checked again, right now
            skipped.append({"path": path, "reason": "it contains video now"})
            continue
        try:
            shutil.rmtree(path)
            deleted.append(path)
        except OSError as error:
            skipped.append({"path": path, "reason": str(error)})

    # Take the deleted folders out of the saved results.
    page = MEDIA_PAGES[kind]
    results = page["load"]()
    if results and deleted:
        gone = set(deleted)
        results["strays"] = [s for s in results["strays"] if s["path"] not in gone]
        results["counts"]["strays"] = len(results["strays"])
        page["save"](results)
    notes = media_rescans(kind, load_settings()) if deleted else []
    return {"deleted": len(deleted), "skipped": skipped, "notes": notes}


@app.route("/photos/empty-folders")
def list_photo_empty_folders():
    """Empty folders found by the photo scan that are still safe to delete."""
    results = load_results()
    if not results:
        return {"folders": []}
    folder = Path(results["folder"])
    out = []
    for entry in results.get("empty_folders", []):
        path = Path(entry["path"])
        if path.is_dir() and folder in path.parents and not folder_has_media(path):
            out.append({"name": entry["name"], "path": str(path), **folder_contents(path)})
    return {"folders": out}


@app.post("/photos/empty-folders/delete")
def delete_photo_empty_folders():
    results = load_results()
    if not results:
        return {"deleted": 0, "skipped": []}
    folder = Path(results["folder"])
    allowed = {e["path"] for e in results.get("empty_folders", [])}
    wanted = set((request.json or {}).get("paths", []))
    deleted, skipped = [], []
    for path in wanted:
        p = Path(path)
        if path not in allowed or folder not in p.parents:
            skipped.append({"path": path, "reason": "not in the scan's empty-folder list"})
            continue
        if folder_has_media(p):  # re-checked right now
            skipped.append({"path": path, "reason": "it has photos or videos now"})
            continue
        try:
            shutil.rmtree(p)
            deleted.append(path)
        except OSError as error:
            skipped.append({"path": path, "reason": str(error)})
    if deleted:
        gone = set(deleted)
        results["empty_folders"] = [e for e in results.get("empty_folders", []) if e["path"] not in gone]
        save_results(results)
    return {"deleted": len(deleted), "skipped": skipped, "notes": []}


# ------------------------------------------------------------ rescans
# Buttons on the MOVIES, TV and PHOTO RESULTS pages, plus an automatic Plex
# rescan of the cleaned folder after moving photos.

def plex_signed_in(settings):
    return bool(settings["plex"]["url"] and (settings["plex"]["token"]
                                            or plexbackdoor.is_open(settings)))  # backdoor


_plex_photo_cache = {}  # (url, token, path_map) -> (time, [local folders]); 5-min cache


def plex_photo_folders(settings):
    """Local folders of the Plex Photos library, mapped to this computer and
    reachable. Empty when Plex isn't set up with a photo library. Cached so the
    photo page doesn't call Plex on every load."""
    if not plex_signed_in(settings):
        return []
    config = settings["plex"]
    key = (config["url"], config.get("token", ""), tuple(sorted(config["path_map"].items())))
    hit = _plex_photo_cache.get(key)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    folders = []
    try:
        for library in plex.libraries(config["url"], plex_client_id(), config["token"], timeout=3):
            if library["type"] != "Photos":
                continue
            for server_folder in library["folders"]:
                local = translate(server_folder, config["path_map"])
                if local and reachable(str(local)) and str(local) not in folders:
                    folders.append(str(local))
    except plex.PlexError:
        folders = hit[1] if hit else []
    _plex_photo_cache[key] = (time.time(), folders)
    return folders


def rescan_plex(settings, library_type, local_folder=None):
    """Ask Plex to rescan its libraries of one type ("Photos", "Movies", "TV").

    With `local_folder`, only the library containing that folder is rescanned,
    and only that folder. Returns a message for the page.
    """
    config = settings["plex"]
    client_id = plex_client_id()
    found = [lib for lib in plex.libraries(config["url"], client_id, config["token"])
             if lib["type"] == library_type]
    if not found:
        return f"PLEX HAS NO {library_type.upper()} LIBRARY"

    if local_folder is None:
        for library in found:
            plex.refresh(config["url"], client_id, config["token"], library["key"])
        return f"PLEX IS RESCANNING: {', '.join(lib['title'] for lib in found)}"

    server_path = to_server_path(local_folder, config["path_map"])
    if server_path is None:
        return "PLEX NOT ASKED TO RESCAN: THIS FOLDER ISN'T MAPPED IN SETUP'S PLEX SECTION"
    for library in found:
        if any(folder_key(server_path).startswith(folder_key(f)) for f in library["folders"]):
            plex.refresh(config["url"], client_id, config["token"], library["key"], path=server_path)
            return f"PLEX IS RESCANNING {server_path}"
    return "PLEX NOT ASKED TO RESCAN: NO PLEX LIBRARY USES THIS FOLDER"


@app.post("/<kind>/scan-folder")
def start_folder_scan(kind):
    """Scan any folder of movies or TV shows: no Radarr/Sonarr needed."""
    if kind not in MEDIA_PAGES:
        abort(404)
    if scan_job["running"]:
        return {"error": "A scan is already running"}, 409
    folder = (request.json or {}).get("folder", "").strip()
    if not folder or not Path(folder).is_dir():
        return {"error": f"Not a folder: {folder}"}, 400
    page = MEDIA_PAGES[kind]
    run_in_background(lambda progress: page["save"](
        with_details(run_folder_scan(folder, kind, progress, FingerprintCache()), progress)))
    return {"ok": True}


@app.route("/movies")
def movies_page():
    return media_page("movies")


@app.post("/movies/scan")
def start_movie_scan():
    return start_media_scan("movies")


@app.route("/tv")
def tv_page():
    return media_page("tv")


@app.post("/tv/scan")
def start_tv_scan():
    return start_media_scan("tv")


# ------------------------------------------------- acting on movie/TV results

def media_roots(results, settings, service):
    """The root folders to move within: the one scanned folder in folder mode,
    otherwise the service's mapped root folders."""
    if results and results.get("mode") == "folder":
        return [Path(results["folder"])]
    return mediamover.root_folders(settings, service)


def media_move_plan(kind, results=None, settings=None):
    page = MEDIA_PAGES[kind]
    results = results if results is not None else page["load"]()
    settings = settings if settings is not None else load_settings()
    if not results:
        return results, []
    roots = media_roots(results, settings, page["service"])
    return results, list(mediamover.things_to_move(results, roots))


def media_group_file(results, group_id, index):
    for group in results.get("groups", []):
        if group["id"] == group_id and 0 <= index < len(group["files"]):
            return group["files"][index]
    abort(404)


@app.post("/<kind>/toggle/<int:group_id>/<int:index>")
def media_toggle(kind, group_id, index):
    """Flip one movie/TV file between KEEP and MOVE."""
    if kind not in MEDIA_PAGES:
        abort(404)
    page = MEDIA_PAGES[kind]
    results = page["load"]()
    file = media_group_file(results, group_id, index)
    if file.get("moved_to"):
        return {"error": "Already moved"}, 409
    file["keep"] = not file["keep"]
    page["save"](results)
    _, plan = media_move_plan(kind, results)
    return {"keep": file["keep"], "to_move": len(plan), "tracked_to_move": mediamover.tracked_in(plan)}


@app.post("/<kind>/stray-move")
def media_stray_move(kind):
    """Tick or untick a stray folder/file for moving."""
    if kind not in MEDIA_PAGES:
        abort(404)
    page = MEDIA_PAGES[kind]
    data = request.json or {}
    path, wanted = data.get("path"), bool(data.get("move"))
    results = page["load"]()
    changed = False
    for stray in (results or {}).get("strays", []):
        if stray["path"] == path and not stray.get("moved_to") and stray.get("kind") != "empty folder":
            stray["move"] = wanted
            changed = True
    if not changed:
        return {"error": "That stray isn't in the current scan"}, 404
    page["save"](results)
    _, plan = media_move_plan(kind, results)
    return {"move": wanted, "to_move": len(plan), "tracked_to_move": mediamover.tracked_in(plan)}


@app.post("/<kind>/move")
def media_move(kind):
    """Move everything ticked. Default: the per-app folder (or _review if unset).
    mode "location": into a browsed folder, for relocating / fixing the library."""
    if kind not in MEDIA_PAGES:
        abort(404)
    page = MEDIA_PAGES[kind]
    settings = load_settings()
    data = request.json or {}
    if data.get("mode") == "location":
        destination = str(data.get("path", "")).strip()
        if not destination or not Path(destination).is_dir():
            return {"error": "Pick a folder to move into"}, 400
    else:
        destination = settings[page["service"]].get("move_to", "").strip() or None
    results, plan = media_move_plan(kind, settings=settings)
    if not plan:
        return {"moved": 0, "notes": ["NOTHING TICKED TO MOVE"]}
    count, notes = mediamover.apply_moves(results, settings, page["service"], plan, destination)
    page["save"](results)
    where = destination if destination else "_REVIEW"
    notes = [f"MOVED {count} ITEM(S) TO {where}"] + notes
    notes += media_rescans(kind, settings)
    return {"moved": count, "notes": notes}


@app.post("/<kind>/undo")
def media_undo(kind):
    if kind not in MEDIA_PAGES:
        abort(404)
    page = MEDIA_PAGES[kind]
    settings = load_settings()
    results = page["load"]()
    restored, skipped = mediamover.undo_last(results, page["service"])
    page["save"](results)
    notes = [f"RESTORED {restored} ITEM(S)"]
    if skipped:
        notes.append(f"{skipped} LEFT IN _REVIEW (SOMETHING WAS ALREADY BACK)")
    if restored:
        notes += media_rescans(kind, settings)
    return {"restored": restored, "skipped": skipped, "notes": notes}


def media_rescans(kind, settings):
    """Ask Radarr/Sonarr and Plex to rescan after a move or undo."""
    page = MEDIA_PAGES[kind]
    service, app_name = page["service"], page["app"]
    notes = []
    config = settings[service]
    if config["url"] and config["api_key"]:
        try:
            arr.rescan(config["url"], config["api_key"], app_name)
            notes.append(f"{app_name.upper()} IS RESCANNING ITS FOLDERS")
        except arr.ArrError as error:
            notes.append(f"COULDN'T ASK {app_name.upper()} TO RESCAN: {error}")
    library = "Movies" if kind == "movies" else "TV"
    if settings["plex"]["rescan_after_move"] and plex_signed_in(settings):
        try:
            notes.append(rescan_plex(settings, library))
        except plex.PlexError as error:
            notes.append(f"COULDN'T ASK PLEX TO RESCAN: {error}")
    return notes


# ---------------------------------------------------------------- results page

@app.route("/results")
def index():
    """Old address for photo results: they're on the PHOTO SCAN page now."""
    return redirect(url_for("start", _anchor="results"))


@app.post("/toggle/<int:group_id>/<int:index>")
def toggle(group_id, index):
    """Flip one file between KEEP and MOVE. Called by the page's JavaScript."""
    results = load_results()
    file = get_file(results, group_id, index)
    if file.get("moved_to"):
        return {"error": "Already moved"}, 409
    file["keep"] = not file["keep"]
    save_results(results)
    return {"keep": file["keep"], "to_move": len(list(files_to_move(results)))}


@app.post("/move")
def move():
    results = load_results()
    settings = load_settings()
    in_plex = plex_signed_in(settings) and to_server_path(results["folder"], settings["plex"]["path_map"]) is not None
    count, plex_note = move_extras(results, write_plexignore=in_plex)
    save_results(results)
    flash(f"MOVED {count} FILES TO _REVIEW")
    if plex_note:
        flash(plex_note)
    if count and settings["plex"]["rescan_after_move"] and plex_signed_in(settings):
        try:
            flash(rescan_plex(settings, "Photos", local_folder=results["folder"]))
        except plex.PlexError as error:
            flash(f"COULDN'T ASK PLEX TO RESCAN: {error}")
    return redirect(url_for("start", _anchor="results"))


@app.post("/undo")
def undo():
    results = load_results()
    restored, skipped = undo_last(results)
    save_results(results)
    message = f"RESTORED {restored} FILES"
    if skipped:
        message += f" // {skipped} LEFT IN _REVIEW (A FILE WAS ALREADY THERE)"
    flash(message)
    settings = load_settings()
    if restored and settings["plex"]["rescan_after_move"] and plex_signed_in(settings):
        try:
            flash(rescan_plex(settings, "Photos", local_folder=results["folder"]))
        except plex.PlexError as error:
            flash(f"COULDN'T ASK PLEX TO RESCAN: {error}")
    return redirect(url_for("start", _anchor="results"))


@app.route("/thumb/<int:group_id>/<int:index>")
def thumbnail(group_id, index):
    path = get_path(load_results(), group_id, index)
    try:
        data = make_thumbnail(str(path), path.stat().st_mtime)
    except FileNotFoundError:  # moved or renamed since the scan: clicking it traces it
        data = no_preview_image("SIGNAL LOST")
    except UNREADABLE:  # damaged photo: not a bug
        data = no_preview_image()
    return send_file(io.BytesIO(data), mimetype="image/jpeg")


@lru_cache(maxsize=4)
def no_preview_image(text="NO PREVIEW"):
    """A small dark picture with a message, for photos that can't be shown."""
    img = Image.new("RGB", THUMB_SIZE, (0, 0, 0))
    from PIL import ImageDraw
    ImageDraw.Draw(img).text((160 - 3 * len(text), 150), text, fill=(51, 255, 102))
    buffer = io.BytesIO()
    img.save(buffer, "JPEG", quality=80)
    return buffer.getvalue()


@app.route("/file/<int:group_id>/<int:index>")
def original(group_id, index):
    results = load_results()
    path = get_path(results, group_id, index)
    if not path.exists():
        if get_file(results, group_id, index).get("moved_to"):
            abort(404)  # gone from _review: nothing to trace
        return redirect(url_for("trace_page", group_id=group_id, index=index))
    return send_file(path)


@app.get("/trace/<int:group_id>/<int:index>")
def trace_page(group_id, index):
    """A file moved or renamed since the scan: the page that hunts for it."""
    results = load_results()
    file = get_file(results, group_id, index)
    return render_template("trace.html", file=file, group_id=group_id, index=index,
                           folder=results["folder"],
                           is_video=Path(file["path"]).suffix.lower() in VIDEO_TYPES)


# What the last trace of each file found, waiting for RECOVER. Kept here on
# the server, so the browser can only ask "recover what you found".
pending_traces = {}


@app.post("/trace/<int:group_id>/<int:index>")
def trace_run(group_id, index):
    """Sweep the scanned folder for this file (and any other lost ones).
    Nothing changes until RECOVER is pressed."""
    results = load_results()
    target = get_file(results, group_id, index)
    answer = tracer.trace(results, target, FingerprintCache(), format_size)
    pending_traces[(group_id, index)] = {"folder": results["folder"], "path": answer["path"],
                                         "matches": answer.pop("matches")}
    answer["recoverable"] = len(pending_traces[(group_id, index)]["matches"])
    return answer


@app.get("/trace/<int:group_id>/<int:index>/preview")
def trace_preview(group_id, index):
    """The traced file, where it was found, for the preview under the trace."""
    found = pending_traces.get((group_id, index))
    if not found or not found["path"]:
        abort(404)
    path = Path(found["folder"]) / found["path"]
    if not path.exists():
        abort(404)
    return send_file(path)


@app.post("/trace/<int:group_id>/<int:index>/recover")
def trace_recover(group_id, index):
    """Update the results with where the traced files are now."""
    found = pending_traces.pop((group_id, index), None)
    if not found:
        return {"error": "Nothing to recover; run the trace again"}, 409
    results = load_results()
    if results["folder"] != found["folder"]:
        return {"error": "The results changed since the trace; run it again"}, 409
    cache = FingerprintCache()
    updated = tracer.recover(results, found["matches"], cache)
    save_results(results)
    cache.save()
    return {"updated": updated}


# ---------------------------------------------------------------- errors and bug reports

@app.errorhandler(Exception)
def unexpected_error(error):
    """Any crash in a page or button: log it, then show the themed error page
    (or, for the page's background requests, a short error with the log id)."""
    if isinstance(error, HTTPException):
        return error  # normal "not found" etc., not a bug
    try:
        error_id = errorlog.record_error(f"{request.method} {request.path}", error, load_settings())
    except Exception:
        error_id = None
    if request.method != "GET" or request.path.startswith(("/scan/status", "/setup/", "/thumb/")):
        return jsonify(error=f"Unexpected error: {error}", error_id=error_id), 500
    return render_template("error.html", error=error, error_id=error_id), 500


@app.post("/client-error")
def client_error():
    """Errors in the page's own scripts, sent by the error catcher in layout.html."""
    data = request.json or {}
    message = str(data.get("message", "Unknown browser error"))[:500]
    details = "\n".join(str(data.get(key, "")) for key in ("page", "source", "stack"))[:6000]
    error_id = errorlog.record_error(f"browser script on {str(data.get('page', '?'))[:200]}",
                                     f"Browser error: {message}", details=details)
    return {"error_id": error_id}


@app.get("/errors")
def errors_page():
    """Every error logged on this computer, open and dismissed."""
    return render_template("errors.html", errors=errorlog.all_errors())


@app.post("/bug/<error_id>/dismiss")
def dismiss_bug(error_id):
    errorlog.mark_reviewed(error_id)
    return {"ok": True}


@app.post("/bug/<error_id>/restore")
def restore_bug(error_id):
    errorlog.mark_unreviewed(error_id)
    return {"ok": True}


@app.post("/bugs/dismiss-all")
def dismiss_all_bugs():
    for error_id in errorlog.unreviewed_errors():
        errorlog.mark_reviewed(error_id)
    return {"ok": True}


def report_repo():
    return load_settings()["bug_report_repo"] or errorlog.DEFAULT_REPO


@app.route("/bug/<error_id>")
def bug_page(error_id):
    """Shows exactly what a bug report would contain, with a link to GitHub."""
    report = errorlog.bug_report(error_id, load_settings())
    if report is None:
        abort(404)
    title, body = report
    repo = report_repo()
    waiting = errorlog.unreviewed_errors()  # looking doesn't dismiss: only DISMISS does
    others = [other for other in waiting if other != error_id]
    return render_template(
        "bug.html", error_id=error_id, title=title, body=body, repo=repo,
        dismissed=error_id not in waiting, next_error=others[0] if others else None,
        others=len(others),
        issue_url=errorlog.github_issue_url(repo, title, body) if repo else None,
        log_file=str(errorlog.log_path(error_id)),
    )


ADDRESS = "http://127.0.0.1:5000"


def open_browser_once():
    """Open the app in the default browser, once per launch.

    In debug mode Flask runs two copies of this file: a watcher that restarts
    the app when code changes, and the app itself (marked WERKZEUG_RUN_MAIN).
    Only the watcher opens the browser, so code changes don't open new tabs.
    The short delay gives the server a moment to start.
    """
    if "--no-browser" in sys.argv or os.environ.get("WERKZEUG_RUN_MAIN"):
        return
    threading.Timer(1.5, lambda: webbrowser.open(ADDRESS)).start()


def log_uncaught_thread_error(info):
    """Errors in any other background thread: log them like everything else."""
    errorlog.record_error(f"background thread {info.thread.name if info.thread else '?'}", info.exc_value)
    threading.__excepthook__(info)


threading.excepthook = log_uncaught_thread_error


# Development only: set HACKON_DEBUG=1 to auto-reload on save and get Flask's
# in-browser debugger. Off by default so the shipped app never exposes it.
DEBUG = os.environ.get("HACKON_DEBUG") == "1"


# --- console theme + quit when the browser closes (desktop-app behaviour) -----
# Each open page pings /alive every few seconds. If no page has pinged for
# EXIT_GRACE seconds the browser is gone, so the app shuts itself down instead of
# lingering as an orphan server. Moving between pages keeps pinging, so it
# survives navigation.
_last_seen = time.time()
EXIT_GRACE = 10  # seconds of silence before the app quits


class _HideHeartbeat(logging.Filter):
    """Keep the 3-second /alive heartbeat out of the request log."""
    def filter(self, record):
        return "/alive" not in record.getMessage()


logging.getLogger("werkzeug").addFilter(_HideHeartbeat())


@app.get("/alive")
def alive():
    """Heartbeat from an open page; resets the shutdown timer."""
    global _last_seen
    _last_seen = time.time()
    return ("", 204)


def watch_for_close():
    """When no page has pinged for a while, the browser is gone: shut down."""
    while True:
        time.sleep(2)
        if time.time() - _last_seen > EXIT_GRACE:
            os._exit(0)


def theme_console():
    """Dress the console window to match the app: green on black, with a banner."""
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.kernel32.SetConsoleTitleW("HackOn Photo & Video DeDupe")
            os.system("color 0A")  # black background, bright green text
        except Exception:
            pass
    print(
        "\n  ==============================================================\n"
        "   HackOn Photo & Video DeDupe   ::   HackOn Systems\n"
        "  ==============================================================\n"
        "   C:\\> SERVER RUNNING  ->  http://127.0.0.1:5000\n"
        "   C:\\> Close the browser window to quit.\n"
    )


if __name__ == "__main__":
    try:
        theme_console()
        open_browser_once()
        if DEBUG:
            app.run(debug=True)  # dev: auto-reload on save + in-browser debugger
        else:
            # App mode: a real WSGI server (no dev-server warning), and quit
            # when the browser closes.
            threading.Thread(target=watch_for_close, daemon=True).start()
            from waitress import serve
            serve(app, host="127.0.0.1", port=5000, threads=8)
    except (Exception, SystemExit) as error:  # e.g. the port is already in use
        # 0 = normal exit. 3 = the auto-reloader restarting the app after a
        # code change (it does this on purpose every time a file is saved).
        if isinstance(error, SystemExit) and error.code in (0, None, 3):
            raise
        error_id = errorlog.record_error("starting the app", error)
        print(f"\n*** The app couldn't start: {error}")
        print(f"*** Logged as {error_id}: see the logs folder. Start the app again to report it.")
        raise
