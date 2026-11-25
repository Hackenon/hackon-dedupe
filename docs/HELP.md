# HackOn Photo & Video DeDupe — Help

A friendly guide to using the app.

## What it does
Finds duplicate and leftover photos, movies and TV in your library, shows them in a retro
green-screen web page, and moves the extras you choose into a `_review` folder — **nothing is
deleted without you**, and every move can be undone. It works on its own, or smarter when you
connect Radarr, Sonarr, and a media server (Plex or Jellyfin).

## The pages
- **PHOTO SCAN** — pick a folder (local or a network share like `\\nas\Photos`) and scan it for
  duplicate photos and videos.
- **MOVIES / TV** — cross-check your library against Radarr / Sonarr to find extra copies and stray
  folders, or **SCAN FOLDER** to scan any folder of movies/TV with no library manager.
- **SETUP** — pick and connect your apps (a media server, Plex or Jellyfin, plus the Radarr/Sonarr library managers), set options, and (first run) discover your servers.
- **ERRORS** — appears only if something went wrong; lists anything logged on this computer.

## Photo scan, step by step
1. On **PHOTO SCAN**, type or BROWSE to a folder, then **RUN SCAN**.
2. Watch the scan "theater" run. When it finishes, the **Summary** and **Results** appear.
3. In each group, the best copy is marked. Click **[X] KEEP / [ ] MOVE** to choose what to keep.
   A group with nothing kept is skipped — you can never move every copy by accident.
4. Press **MOVE** to move the unticked files into `_review`. Press **UNDO** to put the last batch
   back exactly where it was.
5. **Empty folders** — a section lists any folder under your scan with no photos or videos.
   Completely empty ones are ticked for you; folders that still hold other files are shown so you can
   decide. **DELETE SELECTED PERMANENTLY** removes the ticked ones (this one has no undo).

### Kinds of match
- **Exact duplicates** — byte-for-byte identical files.
- **Copies** — the same photo re-saved/resized; the highest-resolution one is kept by default.
- **Similar shots** — burst/near-identical shots; nothing is pre-selected, you choose.

## Movies & TV
With Radarr/Sonarr connected, the app knows exactly which file each movie/episode "really" is, so
it can tell real copies from leftovers.

**No Radarr/Sonarr?** Use **SCAN FOLDER** to scan any folder of movies or TV directly — it finds the
same title in several files, byte-identical files, and (movies) several videos in one folder; you
choose what to keep. When a media server is connected, one-click **library-folder shortcuts** let
you scan a Plex or Jellyfin library folder without typing a path.
- **Extra copies** — other video files in a tracked folder. The tracked file starts as KEEP.
- **Stray folders / loose files** — folders or files that belong to no movie/episode. Each shows
  where it is (**AT:** its full path) and, when known, where Radarr/Sonarr keeps the real copy, so
  you can decide what to do. Tick to move.
- **Empty folders** — their own section, listing folders with no video. Completely empty ones are
  pre-ticked; folders that still hold files (posters, `.nfo`) are shown and left unticked.
  **DELETE SELECTED PERMANENTLY** removes the ticked ones (no undo).
- **Two move options** — **MOVE → DEFAULT** sends ticked items to the per-app default move folder
  (set in **Setup > Options**; when it's blank they go to a `_review` folder inside each root, with
  `_review/*` added to `.plexignore`, or an `.ignore` file for Jellyfin). **MOVE TO LOCATION…** browses to a folder to relocate a stray
  (for example to fix the library). Radarr/Sonarr and your media server (Plex or Jellyfin) rescan after either; **UNDO** puts the last
  batch back.
- **Fast byte-identical check** — for files over 100 MB the scan compares the first and last 50 MB
  (smaller files are read in full), so large libraries over a network scan quickly. A match found
  this way is flagged **"likely identical -- not fully verified"**, with a **VERIFY (FULL HASH)**
  button that reads the whole files to confirm (or shows which ones actually differ). It streams to
  the scan theater and shows a time estimate.
- **Tracked-file warning** — if you tick a file Radarr/Sonarr still tracks, you're warned, because
  moving it may make them re-download it.

## If a file was moved or renamed after a scan (the "trace")
Open a photo that's since moved and the app runs **TRACE.EXE**: it sweeps the scanned folder to
find the file again (by timestamp, picture fingerprint or exact match), shows it, and offers to
**RECOVER** — which just updates where the results look. No files are moved by a trace.

## Setup
Pick each app from its dropdown — a **media server** (Plex or Jellyfin) and a **movie/TV library
manager** (Radarr/Sonarr). An app's settings appear only once you select it; apps that aren't built
yet (Emby, Medusa/SickGear) show as **coming soon**.

- **Radarr / Sonarr** — enter the address and API key (Settings > General > Security in each app).
  **TEST CONNECTION** checks it and maps your folders. **GRAB KEY FROM SERVER** can read the key
  automatically if that server allows local access without a sign-in (with a warning about what
  that means).
- **Plex** — **SIGN IN WITH PLEX** uses Plex's own page (your password never reaches the app), or
  **PROBE FOR BACKDOOR** if Plex trusts your network. You can revoke access anytime in your Plex
  account's Authorized Devices.
- **Jellyfin** — enter the address (e.g. `http://localhost:8096`) and an **API key** created in
  Jellyfin's **Dashboard > API Keys**. **TEST CONNECTION** checks it and maps your library folders.
  (The same key works for Emby, which is coming soon.)
- **PROBE LOCAL NETWORK** (first run) — scans only your own network for Radarr, Sonarr, Plex, Jellyfin/Emby and Medusa/SickGear, and
  offers to fill them in. Same-server addresses are grouped and the faster one is marked.
- **Options** — grouped into sub-sections: **Video details** (read after a scan or during every
  scan), **FFprobe** (**GET FFMPEG** downloads the video-detail tool for you — no manual install),
  **Default move locations** (a per-app folder for moved Movies/TV files), **Bug reports**, and
  **Security** (key storage and an HTTP warning). Each Settings section (Radarr, Sonarr, Plex,
  Options) folds so you can collapse what you're not using.

## Bug reports
If something unexpected breaks, it's logged on **this computer only** — a banner says so and
**nothing is sent**. **REVIEW & REPORT** shows exactly what a report contains (API keys, network
addresses and your Windows username are removed; file/folder names are not), and you submit it on
GitHub yourself, or dismiss it.

## Troubleshooting
- **Movies/TV manager scan unavailable** — connect Radarr/Sonarr in Setup for the smart scan; you can still **SCAN FOLDER** on any folder without them.
- **"NOT CHECKED" items** — Radarr/Sonarr point at a folder the app can't reach; map that root
  folder in Setup, then scan again.
- **No preview / SIGNAL LOST thumbnail** — the file moved or was renamed; click it to trace it.
- **ffprobe not found** — open **Setup > Options** and click **GET FFMPEG**; it downloads the tool
  for you (one click, no winget). The video-details column is optional — duplicate-finding works
  without it.
- **App won't start / "port in use"** — another copy is running; close it, or it's logged as a
  start-up error.

## Your data
Everything stays on your computer. Settings and results are local files; API keys and the Plex
sign-in live in your OS keychain. See INSTALL.md for exact locations.
