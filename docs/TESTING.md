# Testing & verification process

How this project is verified. The goal is a regression net for the **logic core**
(hard-coded input -> expected-output tests of the functions that actually carry
risk), plus a disciplined process for the parts that can't be unit-tested.

Not everything gets a test. Trivial getters, thin wrappers, string formatting with
no branching, and Flask route/template plumbing are excluded on purpose.

## Five verification tiers (run on every change)

**Tier 1 - Static (always).**
- `py_compile` + `symtable` scope analysis on every Python edit. `py_compile` catches
  syntax; `symtable` catches undefined names (this is what flagged a missing
  `import providers`). Syntax-only checking is not enough.
- Edits are exact-match with a uniqueness assert (the old text must occur exactly
  once) so a change never lands in the wrong place silently.
- `grep` the result to confirm the change is where it should be and nowhere else.

**Tier 2 - Unit tests for pure logic (the committed suite).**
Hard-coded tests of the major functions, run with the standard library only
(`python -m unittest`) so there is no third-party dependency and they run the same
on Linux and Windows. Fixtures are temp dirs/files (`tempfile`) and canned
JSON/HTML strings. No live services are touched.

**Tier 3 - Runtime tracing (for what can't be executed).**
Before shipping a flag, mode, or feature, trace every code path it touches at run
time - not just "does the value parse." Enumerate: which branch runs (e.g. DEBUG
vs app mode), which background threads start, and whether the new thing breaks an
assumption any of them make. Lesson: `--no-browser` compiled and parsed fine, but
the close-watchdog thread still ran with no page to heartbeat `/alive`, so the app
exited after `EXIT_GRACE` seconds. The watchdog was right there; the miss was not
tracing the interaction.

**Tier 4 - Quarantine the untestable surface.**
Some things can only be verified on the target machine: the packaged `.exe`,
PyInstaller, Inno Setup/ISCC, the GUI/browser, watchdog timing, the NAS/SMB scan,
and the real Radarr/Sonarr/Jellyfin/Plex. For these:
- say plainly what was verified here vs what only a real run can confirm;
- shrink the blast radius (e.g. keep risky Inno Pascal in one deletable `[Code]`
  block, so a fix is trivial);
- hand over the **cheapest** check first (a compile-only `iscc installer\hackon.iss`
  catches a Pascal error in seconds, instead of after a full `--clean` rebuild).

**Tier 5 - "Done" checklist before calling an artifact finished.**
- No commented-out placeholder that affects the deliverable (e.g. a disabled icon
  line while shipping the installer).
- Product/naming consistency (`grep` for the name; no bare short-name leaks).
- Every documented promise matches an actually-traced code path (don't write "the
  flag works" in a doc for a path that was never run).

## What counts as "major" (gets a unit test)

- **exact.py** - sampled vs full fingerprint: <=100 MB fully hashed; larger uses
  first+last 50 MB plus the size; identical head/tail/size collide under sampling,
  and full-hash VERIFY still separates them. The core duplicate-detection promise.
- **near.py** - perceptual-hash near-duplicate engine: Hamming `distance`,
  `group_look_alikes` union-find clustering (incl. transitive chaining),
  `best_first` quality ranking, and the copies-vs-similar split. As central
  as exact.py for a photo tool.
- **providers.py** - registry resolution (`is_available`, `role_of`, `for_role`,
  `options_for`, `discovery_targets`). Picker and dispatch depend on it.
- **settings.py** - the migration (`_infer_roles`) and `active_type` / `role_config`.
  Migrations are classic silent-breakage sources.
- **API parsers** - `jellyfin._auth_header` and `_parse_libraries`, and the
  arr/plex/netscan confirm-and-parse helpers, against canned payloads. (A header
  test would have caught the Jellyfin auth-format bug.)
- **deleted.py** - tombstone record/load and the `original_path|size` dedup rule.
- **cache.py** - FingerprintCache key format and size/mtime invalidation.
- **perf.py** - `estimate_label` formatting and the read-speed EMA.
- **helpdocs.py** - the Markdown->HTML renderer (headings, lists, code, tables,
  inline escape/code/bold/links), incl. the entity-escaping behaviour we hit.
- **safejson.py** - read/write round-trip, default fallback, broken-file set-aside,
  atomic write. The persistence backbone.
- **plex.py** - response parsers (libraries, server info, PIN check), network stubbed.
- **mover.py / mediamover.py** - free_path, move selection, the move->undo round-trip,
  and `root_for` path-mapping (case-insensitive, most-specific root, prefix boundary).

## Excluded (not worth a unit test)

Thin wrappers and getters; Flask routes and template rendering; orchestration that
only dispatches to I/O (`mediaserver`, `libmanager`, and the move-execution halves
of `mover`/`mediamover`); and anything
requiring the real world (live media servers, the browser, the NAS, PyInstaller,
Inno Setup).

## Remaining (not unit-tested, by design)

The logic core above is covered. What is left is either not pure logic or low
risk, and is verified by the manual smoke test on the target machine:
- **Minor pure-ish helpers** (netpaths address parsing, results shaping, tracer
  moved-file search) could be added for exhaustive coverage - lower value, more coupled.
- **Filesystem scanning** (scan, folderscan, moviescan, tvscan), **ffprobe/video
  details** (mediadetails, mediatools, playback, ffmpegsetup), **dispatch/orchestration**
  (reviewcleanup, mediaserver, libmanager), and **infra** (paths, vault, errorlog):
  I/O- or external-tool-bound, not suited to unit tests.

## Layout & running

- Tests live in `tests/`, one file per area (`test_exact.py`, `test_near.py`,
  `test_providers.py`, `test_settings.py`, `test_parsers.py`, `test_deleted.py`,
  `test_cache.py`, `test_perf.py`, `test_helpdocs.py`, `test_safejson.py`,
  `test_plex.py`, `test_mover.py`, `test_mediamover.py`).
- Run them all: `python -m unittest discover tests`
- **Status:** suite green -- 97 tests across exact, near, providers, settings,
  parsers (jellyfin/arr/netscan/plex), deleted, cache, perf, helpdocs, safejson,
  mover, mediamover.
- Run one area: `python -m unittest tests.test_exact`
- Run before `python changelog.py` on any change that touches the functions above.

## The boundary (important)

The unit suite is the regression net for pure logic. It does **not** cover the
Windows/GUI/installer/NAS surface - that still needs a manual smoke test on the
target machine. The two are complementary: unit tests catch logic regressions
cheaply; the smoke test catches integration and toolchain issues. Neither replaces
the other.
