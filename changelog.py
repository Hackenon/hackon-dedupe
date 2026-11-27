#!/usr/bin/env python
# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Review, approve, and commit — then reset the running changelog.

Workflow:
  1. Work accumulates as notes in CHANGELOG.pending.md. Review it any time.
  2. Set the `Summary:` line (that becomes the commit's first line).
  3. Run:  python changelog.py
     It shows the commit message and the exact files that will be committed,
     then asks you to confirm. On "yes" it runs `git add -A` and commits with
     the changelog as the message, then archives the notes to
     CHANGELOG.archive.md (local, never lost) and resets the pending file.

  python changelog.py --show   # just print the pending notes, do nothing else

Both CHANGELOG.pending.md and CHANGELOG.archive.md are gitignored, so they are
never part of what gets committed. The script works from anywhere in the repo.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path


def _repo_root():
    """The top of the git repo this script lives in (so it works from any
    subfolder); falls back to the script's own folder outside a repo."""
    here = Path(__file__).resolve().parent
    out = subprocess.run(["git", "-C", str(here), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if out.returncode == 0 and out.stdout.strip():
        return Path(out.stdout.strip())
    return here


ROOT = _repo_root()
PENDING = ROOT / "CHANGELOG.pending.md"
ARCHIVE = ROOT / "CHANGELOG.archive.md"

SUMMARY_HINT = "<one line describing this batch; this becomes the commit's first line>"

TEMPLATE = f"""# Pending changelog

Changes since the last commit. Review these and set the Summary line, then run
`python changelog.py` to commit and reset this file.

Summary: {SUMMARY_HINT}
"""


def git(*args, check=False):
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and out.returncode != 0:
        raise RuntimeError((out.stderr or out.stdout).strip())
    return out


def parse(text):
    """Return (summary, note_lines, commit_body) from the pending file."""
    summary = ""
    notes = []
    for ln in text.splitlines():
        low = ln.lower()
        if low.startswith("summary:") and not summary:
            summary = ln.split(":", 1)[1].strip()
        elif ln.startswith("### ") or ln.startswith("- "):
            notes.append(ln)
    # commit body: section headers as plain lines, blank line before each
    body = []
    for ln in notes:
        if ln.startswith("### "):
            if body:
                body.append("")
            body.append(ln[4:].strip())
        else:
            body.append(ln)
    return summary, notes, "\n".join(body)


def main():
    if not PENDING.exists():
        PENDING.write_text(TEMPLATE, encoding="utf-8")
        print("No pending changelog yet; created an empty one.")
        return

    text = PENDING.read_text(encoding="utf-8")
    summary, notes, body = parse(text)

    if "--show" in sys.argv:
        print(text)
        return

    if not notes:
        print("Nothing to commit: the pending changelog has no notes yet.")
        return
    if not summary or summary == SUMMARY_HINT:
        print("Set the `Summary:` line in CHANGELOG.pending.md first — that is the\n"
              "commit's first line. Then run this again.")
        return

    # Show exactly what `git add -A` would stage, so nothing unexpected rides along.
    status = git("status", "--short").stdout.strip()
    if not status:
        print("Nothing to commit: the working tree is clean "
              "(the changelog files are gitignored).")
        return

    message = f"{summary}\n\n{body}\n"
    print("=" * 70)
    print(message, end="")
    print("=" * 70)
    print("Files that will be committed (git add -A):")
    print(status)
    print("=" * 70)
    answer = input("Changelog reviewed and approved? Commit everything above with "
                   "this message? [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        print("Nothing committed. Pending changelog left as-is.")
        return

    # Stage everything (like `git add .`) and commit with the changelog message.
    try:
        git("add", "-A", check=True)
    except RuntimeError as error:
        print(f"git add failed, nothing committed: {error}")
        return
    # Commit with the message on stdin so multi-line formatting is preserved.
    commit = subprocess.run(["git", "commit", "-F", "-"], cwd=ROOT, input=message,
                            capture_output=True, text=True)
    if commit.returncode != 0:
        detail = (commit.stderr or commit.stdout).strip()
        print(f"Commit failed, nothing archived: {detail}")
        return
    print(commit.stdout.strip())

    # The commit is done; archiving/resetting is best-effort. A problem here
    # must not look like the commit failed.
    try:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        short = git("rev-parse", "--short", "HEAD").stdout.strip()
        header = f"\n## {stamp}" + (f"  ({short}) {summary}" if short else f"  {summary}")
        with ARCHIVE.open("a", encoding="utf-8") as f:
            f.write(header + "\n" + "\n".join(notes) + "\n")
        PENDING.write_text(TEMPLATE, encoding="utf-8")
        print(f"Committed, archived {len(notes)} line(s) to {ARCHIVE.name}, and reset "
              f"{PENDING.name}.")
    except OSError as error:
        print(f"Commit succeeded, but tidying the changelog failed: {error}\n"
              f"Your commit is safe; reset CHANGELOG.pending.md by hand if needed.")


if __name__ == "__main__":
    main()
