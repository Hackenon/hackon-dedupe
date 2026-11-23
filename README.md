# HackOn Photo & Video DeDupe

Find duplicate and near-duplicate photos and videos, review them side by side
in a retro green-screen web interface, and move the extras out of the way,
with a full undo.

> **Status:** early development. Works on Windows; Mac support is planned.

## What it finds

| Kind | What it means | Default choice |
|---|---|---|
| **Exact duplicates** | Byte-for-byte identical files (photos or videos), even with different names | Keep one, move the rest |
| **Copies** | The same photo saved again: resized, re-compressed, re-downloaded | Keep the highest resolution |
| **Similar shots** | Burst or back-to-back shots that look almost the same | Keep everything; you untick the ones you don't want |

## Safety first

- **Duplicates are never deleted.** Files you untick are *moved* to a `_review` folder
  inside the scanned folder, keeping their subfolder structure. You delete
  them yourself when you're sure. The one exception is **Remove empty folders**
  on the Movies/TV pages: folders you tick there are deleted permanently, after
  you see their contents and confirm.
- **Undo** puts the last batch of moved files back exactly where they were.
- **A group with nothing ticked is skipped**, so you can't accidentally move every copy.
- **Moves never overwrite** an existing file.
- **System files are ignored:** Synology `@eaDir` thumbnails, `#recycle`, `Thumbs.db`,
  `.DS_Store`, Mac `._` files.

## Quick start

Requires Python 3.10 or newer.

```
python -m venv .venv
.venv\Scripts\activate          (Mac: source .venv/bin/activate)
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000**, pick a folder (it works with network
shares like `\\nas\photos`), and press **RUN SCAN**.

The app only listens on your own computer (`127.0.0.1`), so nothing on your
network can reach it. It also refuses requests that come from other websites
open in your browser (see *Security and privacy* below).

## How it works

1. **Scan** (`scan.py`) walks the folder and sorts files into photos, videos and others.
2. **Exact duplicates** (`exact.py`) group files by size first (instant), then
   compare SHA-256 fingerprints only for files that share a size.
3. **Look-alikes** (`near.py`) give each photo a 64-bit *perceptual hash*, a
   fingerprint of what it looks like, and group photos whose fingerprints
   differ by only a few bits.
4. **Results** (`results.py`) are saved to `results.json`; fingerprints are cached
   in `fingerprints.json`, so rescans only read new or changed files.
5. **The web app** (`app.py`, Flask) shows the groups, saves your Keep/Move
   choices, and moves files (`mover.py`) with a log for undo.

## Movie duplicates (Radarr)

With Radarr connected on the setup screen, **[3] MOVIES** compares every movie
Radarr knows with what's actually in its folder. It lists untracked extra copies
(next to the file Radarr tracks), stray folders and loose files (with a suggested
matching movie), and missing folders. It is read-only. Trailers, featurettes,
samples and other extras are ignored.

## Setup screen

The first time the app opens, it shows a **SETUP** screen for optional connections
(currently Radarr; Plex and Sonarr are planned). Photo scanning works without
any of them, so you can skip it. Settings are saved to `settings.json`; API keys
are never sent back to the browser.

## Security and privacy

- **Only this computer, only this app.** The app listens on `127.0.0.1` and answers
  only to that name, and it refuses button presses that come from any other
  website (protection against cross-site requests and DNS rebinding).
- **Keys are locked away.** Radarr/Sonarr API keys and the Plex sign-in are kept in
  Windows Credential Manager or the Mac Keychain (via the `keyring` package), not in
  `settings.json`. Setup shows where they are.
- **Plex sign-in** uses Plex's own sign-in page; your password never reaches the app.
  The sign-in covers your whole Plex account. To revoke it, sign out in Setup and remove
  "HackOn Photo & Video DeDupe" under Plex > Account Settings > Authorized Devices.
- **Plain HTTP on your network.** Radarr, Sonarr and Plex usually run on `http://`
  addresses, so keys cross your home network unencrypted. Use `https://` addresses
  if your servers support it.
- **Plex "backdoor".** If you tell Plex to trust your network without sign-in, the app
  can use it, but so can every other device on that network. The app shows a banner
  while it's open.
- **Bug reports are never sent automatically.** You review each one and submit it on
  GitHub yourself. API keys, network addresses and your Windows username are removed;
  **file and folder names are not**, which can reveal your NAS's name, movie and show
  titles, Plex library names and photo folder names. Edit them on GitHub before
  submitting if you'd rather not share them.

## Your data stays yours

The app runs entirely on your computer. Your settings and results
(`settings.json`, `results.json`, `movie_results.json`, `tv_results.json`, `fingerprints.json`, `moves.json`)
and error logs (`logs/`) are local files, kept out of version control by `.gitignore`.

## Built with

| Library | Licence |
|---|---|
| [Flask](https://flask.palletsprojects.com/) | BSD-3-Clause |
| [Pillow](https://python-pillow.org/) | MIT-CMU (HPND) |
| [ImageHash](https://github.com/JohannesBuchner/imagehash) | BSD-2-Clause |
| [NumPy](https://numpy.org/) / [SciPy](https://scipy.org/) | BSD-3-Clause |

*Licence names to be double-checked before release.*

## Licence

**Source-available for inspection.** © 2026 HackOn Systems. All rights reserved.

You're welcome to read and review this code. It is **not** released under an
open-source licence, so copying, redistributing, or reusing it in your own
projects isn't permitted for now. A formal licence may follow.
