# Shipping ffprobe with HackOn (research + design)

*Not legal advice. Reviewed 2026-11-22.*

## Why

The app uses **ffprobe** to read a video's resolution, codec and length. We should
never ask users to run `winget`/`brew` to install part of our own tool. This note
records whether we may ship FFmpeg and how we do it.

## Can we? Yes — under the LGPL

- FFmpeg is **LGPL v2.1+**, with some *optional* parts under the GPL. It is **not**
  available under a proprietary licence at any price.
- The GPL-only parts are the heavy **encoders** (notably `libx264`, `libx265`). We use
  **none** of them — ffprobe only reads metadata — so an **LGPL build** covers us and
  avoids the GPL entirely.
- An LGPL build may be shipped in a commercial / closed app as long as we comply. Because
  we invoke ffprobe as a **separate executable** (not linking its libraries into our
  Python), this is the simplest case.

### LGPL obligations we meet
- Ship the binary **unmodified**.
- Include a copy of the **LGPL licence** and keep FFmpeg's copyright notices
  (`bin/FFMPEG-LICENSE.txt`, pulled from the build; `bin/NOTICE.txt` written by the app).
- A one-line credit ("uses FFmpeg under LGPLv2.1") in the About/Setup, and a link to the
  source/build on the website.

## How we deliver it

**Now — download on demand (implemented).** When ffprobe is missing, **Setup → Options**
shows **GET FFMPEG**. One click downloads an LGPL ffprobe into the app's own `bin/`
folder, checksum-verified, and the app picks it up immediately. No winget, no Homebrew,
no admin, nothing installed system-wide. `bin/` is gitignored (it's fetched, not source).

**Later — bundle in the installer.** When we package the desktop build (`.exe` / `.app`,
on the release checklist), include the platform's LGPL ffprobe inside the installer with
the licence, so there's zero steps even offline. The downloader stays as the fallback.

## Sources (LGPL only)

- **Windows x64:** BtbN FFmpeg-Builds — it publishes separate **gpl** and **lgpl** static
  variants; we take the **lgpl** one and extract just `ffprobe.exe` (~35 MB zip, one file
  kept). Assets and a `.sha256` sidecar live on GitHub releases, so we verify the download.
- **macOS:** *open.* evermeet.cx includes ffprobe but its builds are effectively GPL, and
  it has no native Apple-Silicon build. We will not mislabel a GPL build as LGPL, so macOS
  auto-download waits for a verified **LGPL arm64** ffprobe (most likely our own tiny
  `--disable-gpl` build published to our GitHub releases). Until then, a Mac uses any
  `ffprobe` already on PATH.

## Patents (noted, low exposure)

H.264/HEVC carry patent licensing in the abstract, but ffprobe only parses headers (no
full decode/encode), and countless shipping apps bundle FFmpeg. Flagged for awareness, not
a blocker.

## Files

- `ffmpegsetup.py` — platform detection, download, checksum, extract, licence/NOTICE, and
  a self-check (`ffprobe -version`).
- `mediadetails.ffprobe_path()` — now prefers `bin/ffprobe` over PATH.
- `app.py` — `POST /setup/get-ffmpeg` (+ `/status`) run the download in the background.
- `templates/setup.html` — the GET FFMPEG button and live progress.
