# Design: surfacing Help & Install in the Setup tab (in theme)

*Proposal only — no code until approved.*

## Goal
Give users the Help and Install guidance **inside the app**, in the green-screen theme, reachable
from Setup, without leaving to GitHub.

## Proposed approach (single-source the content)
Keep `docs/HELP.md` and `docs/INSTALL.md` as the one source of truth (they also serve as the
GitHub README/wiki). Surface them in-app two ways:

1. **A "HELP" section at the bottom of Setup**, built from the same foldable section style the app
   already uses (the `>` toggles). Each `##` heading in HELP.md becomes a collapsible terminal-style
   block, e.g.:
   ```
   > HELP :: PHOTO SCAN, STEP BY STEP            [click to expand]
   > HELP :: MOVIES & TV
   > HELP :: TROUBLESHOOTING
   ```
   Themed like the rest of Setup (phosphor text, `//` comments, cursor).

2. **A top "> HELP" / "> INSTALL" line** in the first-run box and in the nav, linking to a themed
   `/help` page that renders the full guide (same CRT styling, a simple left-hand "chapter" list).

## Implementation sketch (for when approved)
- Add a tiny Markdown→HTML step at render time (or pre-render the docs to an HTML partial at build),
  so the docs stay the single source and the in-app Help never drifts from them.
- A `/help` route rendering `help.html` (extends `layout.html`) with the converted sections.
- In `setup.html`, a collapsible **HELP** panel + a first-run **QUICK START** box summarising
  INSTALL.md's "First run" steps.
- Keep it all behind the existing theme CSS; no new look.

## Why this shape
- Matches the app's existing foldable-section pattern, so it feels native and on-theme.
- Single-sourcing avoids two copies of the help drifting apart.
- Works offline (it's local), consistent with "your data stays on your computer."
