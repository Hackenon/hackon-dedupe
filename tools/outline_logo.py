#!/usr/bin/env python3
# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Regenerate the HackOn logo SVGs with the text traced to vector paths.

DEV TOOL ONLY — not shipped to users and not imported by the app. The app just
serves the finished SVGs in ../assets/ (which contain no fonts, only <path>s),
so end users never need this. Run it only when you want to change the logo's
wording or layout.

Why: the logos were designed with a monospace font, but a distributed logo
shouldn't depend on a font being installed (and Courier New is proprietary).
This traces the text into outlines using the free, Courier-metric-compatible
Liberation Mono, so the result looks the same everywhere and carries no font.

Requirements (install in a throwaway/dev environment, NOT the app venv):
    pip install fonttools
    plus the free Liberation Mono font files (paths below); on Debian/Ubuntu:
    sudo apt-get install fonts-liberation2

Usage:
    python tools/outline_logo.py
    # overwrites ../assets/logo-hackon.svg, logo-hackon-static.svg, icon.svg

To change the wording/colours/layout, edit the build_full()/build_icon()
templates and the text_paths() calls below, then re-run.
"""

from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

ASSETS = Path(__file__).resolve().parent.parent / "assets"
REG = "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf"
BOLD = "/usr/share/fonts/truetype/liberation2/LiberationMono-Bold.ttf"

fonts = {False: TTFont(REG), True: TTFont(BOLD)}
gsets = {k: f.getGlyphSet() for k, f in fonts.items()}
cmaps = {k: f.getBestCmap() for k, f in fonts.items()}
upm = {k: f["head"].unitsPerEm for k, f in fonts.items()}
hmtx = {k: f["hmtx"] for k, f in fonts.items()}


def gname(bold, ch):
    return cmaps[bold].get(ord(ch)) or ".notdef"


def glyph_d(bold, ch):
    pen = SVGPathPen(gsets[bold])
    gsets[bold][gname(bold, ch)].draw(pen)
    return pen.getCommands()


def advance(bold, ch, size):
    return hmtx[bold][gname(bold, ch)][0] * size / upm[bold]


def width(segs, size, ls):
    chars = "".join(t for t, _, _ in segs)
    total = 0
    for i, ch in enumerate(chars):
        idx, bold = i, segs[0][2]
        for t, _fill, b in segs:
            if idx < len(t):
                bold = b
                break
            idx -= len(t)
        total += advance(bold, ch, size) + (ls if i < len(chars) - 1 else 0)
    return total


def text_paths(segs, x, y, size, ls=0, anchor="start", attrs=""):
    """Trace one line of text (a list of (string, fill, bold) segments) to a
    <g> of <path>s, positioned like an SVG <text> with the given anchor."""
    total = width(segs, size, ls)
    penx = x - total / 2 if anchor == "middle" else (x - total if anchor == "end" else x)
    out = ["<g " + attrs + ">"]
    for text, fill, bold in segs:
        scale = size / upm[bold]
        for ch in text:
            d = glyph_d(bold, ch)
            if d.strip():
                out.append('<path transform="translate(%.2f %d) scale(%.5f %.5f)" d="%s" fill="%s"/>'
                           % (penx, y, scale, -scale, d, fill))
            penx += advance(bold, ch, size) + ls
    out.append("</g>")
    return "\n  ".join(out)


BOOT = "C:" + chr(92) + "> HACKON SYSTEMS :: DEDUPE MODULE"
DESC = "PHOTO & VIDEO DEDUPE"
TAG = "// NOW WITH ADVANCED MEDIA RECOVERY"
GREEN, AMBER, DIM = "#2bff6a", "#ffb000", "#1f7a3f"


def build_full(anim):
    t_boot = text_paths([(BOOT, GREEN, False)], 40, 52, 18, 2, attrs='opacity="0.8"')
    t_x2 = text_paths([("x2", DIM, False)], 70, 98, 18)
    t_word = text_paths([("Hack", GREEN, True), ("On", AMBER, True)], 228, 176, 78, 1, attrs='filter="url(#glow)"')
    t_desc = text_paths([(DESC, GREEN, False)], 231, 224, 27, 7, attrs='opacity="0.9"')
    t_tag = text_paths([(TAG, GREEN, False)], 233, 256, 15, 3, attrs='opacity="0.65"')
    cur = ('<rect class="blink" x="560" y="120" width="24" height="60" fill="#ffb000" filter="url(#glow)"/>'
           if anim else '<rect x="560" y="120" width="24" height="60" fill="#ffb000" filter="url(#glow)"/>')
    style = ('    <style>.blink{animation:bl 1.1s steps(1) infinite}@keyframes bl{50%{opacity:0}}'
             '@media(prefers-reduced-motion:reduce){.blink{animation:none}}</style>\n') if anim else ''
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 860 300" width="860" height="300">\n'
        '  <defs>\n'
        '    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">\n'
        '      <feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>\n'
        '    </filter>\n'
        '    <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">\n'
        '      <rect width="4" height="4" fill="#000"/><rect width="4" height="1" fill="#0e2a16" opacity="0.5"/>\n'
        '    </pattern>\n' + style +
        '  </defs>\n'
        '  <rect x="6" y="6" width="848" height="288" rx="16" fill="#05090a" stroke="#2bff6a" stroke-width="2" filter="url(#glow)"/>\n'
        '  <rect x="6" y="6" width="848" height="288" rx="16" fill="url(#scan)" opacity="0.5"/>\n'
        '  ' + t_boot + '\n'
        '  <g filter="url(#glow)">\n'
        '    <rect x="52" y="104" width="116" height="116" rx="10" fill="none" stroke="#1f7a3f" stroke-width="3" stroke-dasharray="7 6"/>\n'
        '    ' + t_x2 + '\n'
        '    <rect x="72" y="124" width="116" height="116" rx="10" fill="#06130b" stroke="#2bff6a" stroke-width="3"/>\n'
        '    <circle cx="112" cy="156" r="11" fill="none" stroke="#2bff6a" stroke-width="3"/>\n'
        '    <path d="M86 214 L118 176 L140 200 L156 184 L174 214 Z" fill="none" stroke="#2bff6a" stroke-width="3" stroke-linejoin="round"/>\n'
        '    <circle cx="170" cy="138" r="16" fill="#06130b" stroke="#ffb000" stroke-width="3"/>\n'
        '    <path d="M164 130 L180 138 L164 146 Z" fill="#ffb000"/>\n'
        '  </g>\n'
        '  ' + t_word + '\n'
        '  ' + cur + '\n'
        '  ' + t_desc + '\n'
        '  ' + t_tag + '\n'
        '</svg>\n')


def build_icon():
    t_word = text_paths([("Hack", GREEN, True), ("On", AMBER, True)], 256, 452, 58, 0, anchor="middle", attrs='filter="url(#g)"')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">\n'
        '  <defs>\n'
        '    <filter id="g" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>\n'
        '    <pattern id="sc" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="#000"/><rect width="6" height="2" fill="#0e2a16" opacity="0.5"/></pattern>\n'
        '    <radialGradient id="crt" cx="50%" cy="42%" r="75%"><stop offset="0%" stop-color="#0a1410"/><stop offset="100%" stop-color="#03070700"/></radialGradient>\n'
        '  </defs>\n'
        '  <rect x="16" y="16" width="480" height="480" rx="96" fill="#05090a" stroke="#2bff6a" stroke-width="8" filter="url(#g)"/>\n'
        '  <rect x="16" y="16" width="480" height="480" rx="96" fill="url(#crt)"/>\n'
        '  <rect x="16" y="16" width="480" height="480" rx="96" fill="url(#sc)" opacity="0.5"/>\n'
        '  <g filter="url(#g)">\n'
        '    <rect x="120" y="150" width="180" height="180" rx="18" fill="none" stroke="#1f7a3f" stroke-width="8" stroke-dasharray="14 12"/>\n'
        '    <rect x="160" y="190" width="180" height="180" rx="18" fill="#06130b" stroke="#2bff6a" stroke-width="9"/>\n'
        '    <circle cx="214" cy="248" r="20" fill="none" stroke="#2bff6a" stroke-width="8"/>\n'
        '    <path d="M178 352 L228 288 L268 322 L298 296 L330 352 Z" fill="none" stroke="#2bff6a" stroke-width="8" stroke-linejoin="round"/>\n'
        '    <circle cx="326" cy="214" r="30" fill="#06130b" stroke="#ffb000" stroke-width="8"/>\n'
        '    <path d="M315 199 L344 214 L315 229 Z" fill="#ffb000"/>\n'
        '  </g>\n'
        '  ' + t_word + '\n'
        '</svg>\n')


def main():
    (ASSETS / "logo-hackon.svg").write_text(build_full(True))
    (ASSETS / "logo-hackon-static.svg").write_text(build_full(False))
    (ASSETS / "icon.svg").write_text(build_icon())
    print("Wrote assets/logo-hackon.svg, logo-hackon-static.svg, icon.svg")


if __name__ == "__main__":
    main()
