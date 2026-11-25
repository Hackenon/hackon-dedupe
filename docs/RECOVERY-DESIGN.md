# Advanced Data Recovery — design note (future feature)

Status: **future / V2.** Research only, no code yet. Captures the plan and the
engineering realities so we build it right when we get to it.

## The idea

Today, when a `_review` item is found missing at load time, we drop its record
from the results JSON. Instead:

1. **Don't delete the record — tombstone it.** Move all known info (fingerprint,
   original path, size, mtime, hashes) into a `deleted_photos.json` /
   `deleted_movies.json` / `deleted_tv.json` file.
2. **Normal trace routine runs first.** If the file is relocated/recoverable by
   our ordinary logic, restore it quietly.
3. **Only if that fails** does an **"Advanced data recovery"** button appear on
   the tab — a slow, admin-requiring, last-resort operation we keep hidden until
   it's actually warranted.

## Two corrections that shaped the design

- **A fingerprint can't scan raw disk bytes.** A perceptual hash (ImageHash) is
  computed from *decoded pixels* — you must reconstruct and decode the file
  first. SHA-256 likewise needs the complete byte range. So the fingerprint
  cannot *drive* a disk scan. Its real job is **triage after recovery**: carving
  tools produce hundreds of nameless files; our stored pHashes pick out the ones
  the user actually wants.
- **Target unallocated space, not slack space.** Slack space holds scraps of
  *older* files. A fully deleted file lives in **unallocated clusters** (freed
  but not yet reused). That's the recovery pool.

## Two recovery methods (everything maps onto these)

1. **Metadata recovery (MFT-based).** NTFS leaves the deleted file's MFT record —
   with pointers to its clusters — intact for a while. Follow the pointers →
   exact file back, original name and path. Fast, lossless, but only while the
   record survives.
2. **File carving (signature-based).** Metadata gone: scan unallocated space for
   headers/footers (JPEG `FFD8…FFD9`, MP4 `ftyp`, …) and carve. Loses filenames,
   and **fails/corrupts on fragmented files** — which large videos usually are.

## Engine options (native-Python question answered)

No pure-Python engine beats the established tools at the actual recovery. Plan:

- **`pytsk3`** (The Sleuth Kit bindings) — the programmatic metadata-recovery
  path. Open the volume, enumerate `UNALLOC` entries, read content via cluster
  runs, all from Python. Use for clean recoveries; verify against stored SHA-256.
- **`dfVFS`** — higher-level Python layer over pytsk3 if we want a nicer API.
- **`deep-recover`** (PyPI, MIT) — reference design: pytsk3 metadata recovery with
  automatic fallback to carving.
- **`ntfsrecover`** — dependency-free pure-Python NTFS recovery; attractive for
  bundling, less battle-tested than TSK.
- **winfr** (Windows File Recovery, Win10 2004+) / **PhotoRec** — invoke as a
  subprocess for the carving fallback. PhotoRec = gold standard for carving but
  does not reassemble fragmented files.

**Recommendation:** pytsk3 for the clean path → winfr/PhotoRec subprocess for the
carving fallback → our fingerprints as the triage layer. Do **not** hand-roll a
carver; reassembling fragmented files is a research-grade problem.

## Three realities that gate the feature

1. **NAS media is out of scope.** Block-level recovery needs raw access to the
   physical volume. Media on an SMB share (`\\192.168.20.72\Plex_Media\...`)
   can't be recovered from the Windows client — it would have to run on the NAS
   itself. **This feature targets local disks only.**
2. **SSDs usually can't be recovered.** With TRIM (all modern Windows system
   drives), freed blocks are zeroed within seconds. "A day later" on an SSD ≈
   gone. The feature pays off on spinning HDDs / NAS platters.
3. **Stop writing to the volume — including our own app.** Recovery must write to
   a *different* drive (winfr enforces this). Our own JSON/log/temp writes to the
   same volume can overwrite the very clusters we're trying to save. The button
   must warn the user to minimise disk activity immediately.

## Tombstone record — fields and what each is for

- **Original full path + filename** — *best* recovery key; what MFT recovery
  (pytsk3 / winfr Regular) matches on for a clean, lossless pull.
- **Exact size + SHA-256** — verify a recovered/carved candidate is byte-identical.
- **Perceptual hash (pHash)** — triage/fallback key; pick the file out of a pile
  of carved candidates, or match a slightly re-encoded survivor.
- **Deletion timestamp** — set honest expectations ("HDD, 1 day ago: good odds"
  vs "SSD: likely gone").

## Packaging notes

- Raw volume access on Windows (`\\.\C:`) requires **administrator elevation**.
- winfr ships only on Windows 10 2004+ (Microsoft Store).
- Bundling TSK binaries or an elevated subprocess complicates a signed installer —
  factor into the build/signing story.
