#!/usr/bin/env python3
# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Rebuild the HackOn Systems website (site/) from the docs. Dev tool.

Renders index.html, install.html and help.html with a shared CRT-themed shell
(company logo in the header), using the app's own dependency-free Markdown
renderer so the Install/Help pages always match docs/INSTALL.md and docs/HELP.md.

    python tools/build_site.py      # overwrites site/*.html
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import helpdocs  # noqa: E402

SITE = ROOT / "site"
GITHUB = "https://github.com/Hackenon"            # the user's GitHub profile
REPO = GITHUB + "/hackon-dedupe"                   # the project repo
DOWNLOAD = REPO + "/releases"


def shell(title, body, active):
    nav = [("index.html", "HOME"), ("install.html", "INSTALL"), ("help.html", "HELP"), ("about.html", "ABOUT")]
    parts = []
    for href, name in nav:
        hi = " style='text-shadow:var(--glow)'" if name == active else ""
        parts.append("<a href='" + href + "'" + hi + ">" + name + "</a>")
    parts.append("<a href='" + REPO + "' target='_blank' rel='noopener'>GITHUB</a>")
    links = "".join(parts)
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>" + title + "</title>\n"
        "<meta name=\"description\" content=\"HackOn Photo &amp; Video DeDupe \u2014 a retro desktop app "
        "that finds duplicate photos and videos and cleans up extra movie/TV copies, safely and locally.\">\n"
        "<link rel=\"icon\" href=\"assets/icon.svg\">\n<link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n"
        "<header class=\"site\"><div class=\"wrap\">\n"
        "  <a class=\"brand\" href=\"index.html\"><img class=\"brandlogo\" src=\"assets/logo-hackon-systems.svg\" alt=\"HackOn Systems\"></a>\n"
        "  <nav>" + links + "</nav>\n</div></header>\n" + body + "\n"
        "<footer class=\"site\"><div class=\"wrap\">\n"
        "  <div>&copy; 2026 HackOn Systems &middot; AGPLv3 &middot; <a href=\"" + REPO + "\" target=\"_blank\" rel=\"noopener\">Source on GitHub</a></div>\n"
        "  <div class=\"fine\">Not affiliated with Plex, Jellyfin, Radarr or Sonarr. Works alongside them.</div>\n"
        "</div></footer>\n</body>\n</html>\n")


def landing():
    features = [
        ("PHOTO DUPLICATES", "Exact copies and look-alikes &mdash; resized, re-saved, or back-to-back burst shots &mdash; found with perceptual fingerprints. Empty folders are listed for cleanup too."),
        ("MOVIES &amp; TV", "Finds extra copies, stray folders and empty folders in your Radarr and Sonarr libraries. Move extras to a default or a browsed location; the file the manager tracks is always kept."),
        ("WORKS WITH PLEX &amp; JELLYFIN", "Hides the review folder from your media server (Plex or Jellyfin) and asks it to rescan after any change, so your library stays in sync."),
        ("SAFE BY DESIGN", "Nothing is ever deleted. Extras move to a <code>_review</code> folder with full undo, and a group is skipped unless something is kept."),
        ("LOCAL &amp; PRIVATE", "Runs on your own PC at <code>127.0.0.1</code>. Your files, API keys and server tokens never leave your machine."),
        ("FREE &amp; OPEN SOURCE", "On GitHub for anyone to read, run and improve. No account, no cloud, no tracking."),
    ]
    cards = "".join("<div class='card'><h3>" + t + "</h3><p>" + d + "</p></div>" for t, d in features)
    prompt = "<span class='prompt'>C:\\&gt;</span>"
    return (
        "\n<section class=\"hero\">\n"
        "  <img class=\"logo\" src=\"assets/logo-hackon.svg\" alt=\"HackOn Photo & Video DeDupe\">\n"
        "  <div class=\"tag\">// ADVANCED MEDIA RECOVERY &mdash; COMING SOON</div>\n"
        "  <p class=\"pitch\">A retro, terminal-styled desktop app that hunts down duplicate and near-duplicate\n"
        "  photos and videos &mdash; and cleans up the extra movie and TV copies hiding in your Radarr, Sonarr,\n"
        "  Plex and Jellyfin libraries. Safely: nothing is deleted, everything can be undone.</p>\n"
        "  <div class=\"btns\">\n"
        "    <a class=\"btn primary\" href=\"" + DOWNLOAD + "\">&#9654; DOWNLOAD</a>\n"
        "    <a class=\"btn\" href=\"install.html\">INSTALL GUIDE</a>\n"
        "    <a class=\"btn\" href=\"" + REPO + "\" target=\"_blank\" rel=\"noopener\">VIEW ON GITHUB</a>\n"
        "  </div>\n</section>\n"
        "<section><div class=\"wrap\">\n  <h2>" + prompt + " WHAT IT DOES</h2>\n"
        "  <div class=\"features\">" + cards + "</div>\n</div></section>\n"
        "<section><div class=\"wrap\">\n  <h2>" + prompt + " GET STARTED</h2>\n"
        "  <p>Read the <a href=\"install.html\">install guide</a> to set it up on Windows or Mac, then the\n"
        "  <a href=\"help.html\">help guide</a> for a walkthrough of every page and scan. When you're ready,\n"
        "  grab the latest build from the <a href=\"" + DOWNLOAD + "\">releases page</a>.</p>\n</div></section>\n")


def about():
    """The About page: the on-brand avatar above the bio (docs/ABOUT.md)."""
    html = helpdocs.render((ROOT / "docs/ABOUT.md").read_text(encoding="utf-8"))
    portrait = ("<img class=\"portrait\" src=\"assets/Billhacker-avatar.svg\" "
                "alt=\"The developer behind HackOn Systems\">\n")
    return "<div class='wrap doc about'>" + portrait + html + "</div>"


def main():
    (SITE / "index.html").write_text(shell("HackOn Photo & Video DeDupe", landing(), "HOME"), encoding="utf-8")
    for src, out, active, title in [
        ("docs/INSTALL.md", "install.html", "INSTALL", "Install \u2014 HackOn Photo & Video DeDupe"),
        ("docs/HELP.md", "help.html", "HELP", "Help \u2014 HackOn Photo & Video DeDupe"),
    ]:
        html = helpdocs.render((ROOT / src).read_text(encoding="utf-8"))
        (SITE / out).write_text(shell(title, "<div class='wrap doc'>" + html + "</div>", active), encoding="utf-8")
    (SITE / "about.html").write_text(
        shell("About \u2014 HackOn Photo & Video DeDupe", about(), "ABOUT"), encoding="utf-8")
    print("built:", ", ".join(sorted(p.name for p in SITE.glob("*.html"))))


if __name__ == "__main__":
    main()
