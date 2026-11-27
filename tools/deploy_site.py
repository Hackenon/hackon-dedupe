# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Deploy the built website into the hackonsystems-site repo. Dev tool.

The marketing site lives in its OWN Git repo (github.com/Hackenon/hackonsystems),
checked out next to this project. The app repo gitignores site/, so the website
is never part of an app-repo push -- it ships from its own repo. This script
rebuilds site/ from the docs and copies the whole site/ tree into that repo, so
you can commit and push it.

    python tools/deploy_site.py                 # rebuild + copy, then print the git steps
    python tools/deploy_site.py --push "msg"    # also commit & push the site repo for you
    python tools/deploy_site.py --no-build      # copy the current site/ as-is (no rebuild)
    python tools/deploy_site.py --dest PATH     # copy somewhere other than the default

Target folder resolution: --dest, else $HACKON_SITE_REPO, else ../hackonsystems-site
(a sibling of this project). The site repo's own .git is never touched by the copy,
and files already in the site repo that are not in site/ are left alone.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def resolve_dest(cli_dest):
    if cli_dest:
        return Path(cli_dest).expanduser().resolve()
    env = os.environ.get("HACKON_SITE_REPO")
    if env:
        return Path(env).expanduser().resolve()
    return (ROOT.parent / "hackonsystems-site").resolve()


def rebuild():
    """Run the existing builder so there is a single source of truth."""
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_site.py")], check=True)


def copy_tree(dest):
    if not SITE.is_dir():
        sys.exit(f"No site/ folder at {SITE}; nothing to deploy.")
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in sorted(SITE.rglob("*")):
        rel = src.relative_to(SITE)
        if ".git" in rel.parts:          # never carry a stray .git into the repo
            continue
        target = dest / rel
        if src.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            copied.append(rel.as_posix())
    return copied


def git_push(dest, message):
    if not (dest / ".git").is_dir():
        sys.exit(f"{dest} is not a Git repo (no .git found). Set it up, or push by hand.")
    subprocess.run(["git", "-C", str(dest), "add", "-A"], check=True)
    if subprocess.run(["git", "-C", str(dest), "diff", "--cached", "--quiet"]).returncode == 0:
        print("Site repo already up to date; nothing to commit.")
        return
    subprocess.run(["git", "-C", str(dest), "commit", "-m", message], check=True)
    subprocess.run(["git", "-C", str(dest), "push"], check=True)
    print("Pushed the site repo -- GitHub Pages will redeploy hackonsystems.com shortly.")


def main():
    ap = argparse.ArgumentParser(description="Rebuild and deploy the HackOn Systems website.")
    ap.add_argument("--dest", help="site repo folder (default: ../hackonsystems-site or $HACKON_SITE_REPO)")
    ap.add_argument("--push", metavar="MESSAGE", help="commit with MESSAGE and push the site repo")
    ap.add_argument("--no-build", action="store_true", help="skip the rebuild; copy site/ as it is")
    args = ap.parse_args()

    dest = resolve_dest(args.dest)
    if not args.no_build:
        rebuild()
    copied = copy_tree(dest)
    print(f"Copied {len(copied)} file(s) into {dest}")

    if args.push:
        git_push(dest, args.push)
    else:
        print("\nNext, publish the site:")
        print(f"  cd {dest}")
        print('  git add -A && git commit -m "Update site" && git push')


if __name__ == "__main__":
    main()
