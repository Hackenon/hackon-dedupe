# HackOn Photo & Video DeDupe
# Copyright (C) 2026 HackOn Systems
#
# This file is part of HackOn Photo & Video DeDupe, licensed under the GNU Affero
# General Public License v3.0 or later. It comes with NO WARRANTY, to the extent
# permitted by law. See the LICENSE file or <https://www.gnu.org/licenses/>.

"""Generate assets/icon.ico (multi-size Windows app icon) in the CRT theme. Dev tool.

Renders a rounded-square CRT frame with the app motif (overlapping photo frames,
lens + mountain, amber play button) echoing assets/icon.svg, and writes a .ico
containing 16-256 px. PyInstaller embeds it in HackOn.exe (hackon-dedupe.spec),
and Inno Setup uses it for the installer (installer/hackon.iss).

    python tools/make_app_icon.py

Pillow only; no SVG rasteriser needed. Re-run after a palette or logo change.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icon.ico"

FRAME_BG = (5, 9, 10)      # #05090a
PHOS     = (43, 255, 106)  # #2bff6a
DIM      = (31, 122, 63)   # #1f7a3f
AMBER    = (255, 176, 0)   # #ffb000
PANEL    = (6, 19, 11)     # #06130b
SCAN     = (14, 42, 22)    # #0e2a16


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size-1, size-1], radius=radius, fill=255)
    return m


def draw_motif(img, cx, cy, s):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    u = s / 2.0
    lw = max(2, int(s * 0.05))
    # dashed back frame (dim)
    d.rounded_rectangle([cx - u, cy - u, cx + u*0.25, cy + u*0.25],
                        radius=int(s*0.08), outline=DIM, width=lw)
    # solid front frame (phosphor)
    fx0, fy0, fx1, fy1 = cx - u*0.25, cy - u*0.25, cx + u, cy + u
    d.rounded_rectangle([fx0, fy0, fx1, fy1], radius=int(s*0.08), fill=PANEL, outline=PHOS, width=lw)
    # lens
    lr = s * 0.10
    lcx, lcy = fx0 + (fx1-fx0)*0.30, fy0 + (fy1-fy0)*0.32
    d.ellipse([lcx-lr, lcy-lr, lcx+lr, lcy+lr], outline=PHOS, width=lw)
    # mountain
    my = fy1 - (fy1-fy0)*0.20
    d.line([(fx0 + (fx1-fx0)*0.14, my),
            (fx0 + (fx1-fx0)*0.42, my - (fy1-fy0)*0.36),
            (fx0 + (fx1-fx0)*0.60, my - (fy1-fy0)*0.14),
            (fx0 + (fx1-fx0)*0.74, my - (fy1-fy0)*0.28),
            (fx0 + (fx1-fx0)*0.88, my)], fill=PHOS, width=lw, joint="curve")
    # amber play button
    pr = s * 0.19
    pcx, pcy = fx1 - u*0.12, fy0 - u*0.02
    d.ellipse([pcx-pr, pcy-pr, pcx+pr, pcy+pr], fill=PANEL, outline=AMBER, width=lw)
    t = pr * 0.5
    d.polygon([(pcx - t*0.55, pcy - t), (pcx + t, pcy), (pcx - t*0.55, pcy + t)], fill=AMBER)
    glow = layer.filter(ImageFilter.GaussianBlur(max(1, int(s*0.015))))
    img.alpha_composite(glow)
    img.alpha_composite(layer)


def render(size):
    S = size
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # frame body on its own layer, then clip to rounded square
    body = Image.new("RGBA", (S, S), FRAME_BG + (255,))
    d = ImageDraw.Draw(body, "RGBA")
    for y in range(0, S, max(2, S // 64)):
        d.line([(0, y), (S, y)], fill=SCAN + (90,), width=1)
    mask = rounded_mask(S, int(S*0.20))
    img.paste(body, (0, 0), mask)
    # green border
    bd = ImageDraw.Draw(img, "RGBA")
    bw = max(2, int(S*0.035))
    bd.rounded_rectangle([bw//2, bw//2, S-1-bw//2, S-1-bw//2],
                         radius=int(S*0.20), outline=PHOS, width=bw)
    draw_motif(img, S*0.52, S*0.50, S*0.60)
    return img


def main():
    master = render(256)
    sizes = [256, 128, 64, 48, 32, 16]
    master.save(OUT, format="ICO", sizes=[(s, s) for s in sizes])
    # also a PNG preview for eyeballing
    master.save(ROOT / "icon-preview.png")
    print(f"Wrote {OUT} with sizes {sizes}")


if __name__ == "__main__":
    main()
