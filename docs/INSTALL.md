# HackOn Photo & Video DeDupe — Install

## Requirements
- **Python 3.10 or newer** (the app is developed on 3.15).
- Windows 10/11 or macOS. A local folder or a network share to scan.
- **FFmpeg / ffprobe** (for video resolution, codec and length) is handled for you:
  on Windows, open **Setup &rarr; Options** and click **GET FFMPEG** &mdash; the app downloads it into
  its own folder (no winget, no admin, nothing installed system-wide). On macOS, if a system
  `ffprobe` is on your PATH the app uses it; a one-click download for Mac is coming. Photo and
  movie/TV duplicate-finding works with or without it &mdash; it only adds the video details column.

## Install & run (from source)
```
# 1. Get the code (download the ZIP or clone the repo), then open a terminal in its folder.

# 2. Make a virtual environment
python -m venv .venv

# 3. Activate it
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run it
python app.py
```
The app opens your default browser at **http://127.0.0.1:5000** automatically. (Start it with
`python app.py --no-browser` to skip that.)

## First run
1. The **SETUP** page opens. You can **SKIP FOR NOW** — photo scanning needs no setup.
2. Optional: on first run, press **PROBE LOCAL NETWORK** to find Radarr/Sonarr/Plex, or enter them
   by hand, then **SAVE SETTINGS**.
3. Go to **PHOTO SCAN**, pick a folder, and **RUN SCAN**.

## Updating
Pull/download the new code, then with the virtual environment active run
`pip install -r requirements.txt` again in case dependencies changed, and start the app.

## Where your data lives (kept out of version control)
| File / folder | What it holds |
|---|---|
| `settings.json` | Your settings and folder shortcuts (API keys/token are in the OS keychain, not here) |
| `results.json`, `movie_results.json`, `tv_results.json` | The latest scan results |
| `fingerprints.json` | Cached photo fingerprints (so rescans are fast) |
| `moves.json`, `movie_moves.json`, `tv_moves.json` | Undo history for moves |
| `logs/` | Error logs (only if something went wrong) |
| `_review/` (inside a scanned/root folder) | Files you moved, waiting for you to delete or undo |

To start completely fresh, close the app and delete those files.

## Uninstall
Delete the app folder (including `.venv`). To also clear saved keys, sign out of Plex in Setup and
remove the app's entries from Windows Credential Manager / macOS Keychain (named `hackon-dedupe`).

## Notes for a future packaged release (not yet available)
A one-click installer (Windows `.exe` / Mac `.app`) with Python and FFmpeg bundled is on the
roadmap, so end users won't need the steps above. Until then, the from-source steps are the way.
