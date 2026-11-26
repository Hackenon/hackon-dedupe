"""Generate the Inno Setup wizard images in the CRT green-phosphor theme. Dev tool.

Renders installer/assets/wizard-large-*.png (welcome/finish left panel) and
wizard-small-*.png (inner-page banner) at several DPI sizes, echoing assets/icon.svg
(overlapping photo frames, lens + mountain, amber play button, Hack=green On=amber).

    python tools/make_installer_art.py

Pillow only; no SVG rasteriser needed. Re-run after a palette or logo change.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "installer" / "assets"

# CRT palette (from site/style.css)
BG      = (4, 23, 10)      # #04170a
BG_CTR  = (10, 20, 16)     # #0a1410 radial centre
SCAN    = (14, 42, 22)     # #0e2a16 scanline
PHOS    = (51, 255, 102)   # #33ff66
DIM     = (31, 122, 63)    # #1f7a3f
AMBER   = (255, 176, 0)    # #ffb000
SOFT    = (189, 236, 203)  # #bdeccb
PANEL   = (6, 19, 11)      # #06130b


def font(size, bold=True):
    names = (["DejaVuSansMono-Bold.ttf", "consolab.ttf", "courbd.ttf"] if bold
             else ["DejaVuSansMono.ttf", "consola.ttf", "cour.ttf"])
    roots = ["/usr/share/fonts/truetype/dejavu", r"C:\Windows\Fonts", "/Library/Fonts"]
    for r in roots:
        for n in names:
            p = Path(r) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def ctext(d, cx, y, text, fnt, fill, spacing=0):
    """Draw letter-spaced text centred on cx; return its height."""
    widths = [d.textlength(ch, font=fnt) for ch in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x = cx - total / 2
    asc, desc = fnt.getmetrics()
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=fnt, fill=fill)
        x += w + spacing
    return asc + desc


def background(w, h):
    img = Image.new("RGB", (w, h), BG)
    # radial-ish centre glow
    glow = Image.new("L", (w, h), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-w*0.3, -h*0.1, w*1.3, h*0.9], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(w*0.25))
    img = Image.composite(Image.new("RGB", (w, h), BG_CTR), img, glow)
    # scanlines
    d = ImageDraw.Draw(img, "RGBA")
    for y in range(0, h, max(3, h // 150)):
        d.line([(0, y), (w, y)], fill=SCAN + (90,), width=1)
    return img


def draw_icon(img, cx, cy, s):
    """Overlapping photo frames + lens + mountain + amber play button, centred."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    u = s / 2.0
    lw = max(2, int(s * 0.045))
    # dashed back frame (dim) -- approximate dashes with a plain rounded rect
    d.rounded_rectangle([cx - u, cy - u, cx + u*0.25, cy + u*0.25],
                        radius=int(s*0.07), outline=DIM, width=lw)
    # solid front frame (phosphor)
    fx0, fy0, fx1, fy1 = cx - u*0.25, cy - u*0.25, cx + u, cy + u
    d.rounded_rectangle([fx0, fy0, fx1, fy1], radius=int(s*0.07), fill=PANEL, outline=PHOS, width=lw)
    # lens circle
    lr = s * 0.09
    lcx, lcy = fx0 + (fx1-fx0)*0.28, fy0 + (fy1-fy0)*0.30
    d.ellipse([lcx-lr, lcy-lr, lcx+lr, lcy+lr], outline=PHOS, width=lw)
    # mountain polyline inside the front frame
    my = fy1 - (fy1-fy0)*0.18
    d.line([(fx0 + (fx1-fx0)*0.12, my),
            (fx0 + (fx1-fx0)*0.40, my - (fy1-fy0)*0.34),
            (fx0 + (fx1-fx0)*0.58, my - (fy1-fy0)*0.12),
            (fx0 + (fx1-fx0)*0.72, my - (fy1-fy0)*0.26),
            (fx0 + (fx1-fx0)*0.88, my)], fill=PHOS, width=lw, joint="curve")
    # amber play button (video), top-right
    pr = s * 0.17
    pcx, pcy = fx1 - u*0.15, fy0 - u*0.02
    d.ellipse([pcx-pr, pcy-pr, pcx+pr, pcy+pr], fill=PANEL, outline=AMBER, width=lw)
    t = pr * 0.5
    d.polygon([(pcx - t*0.6, pcy - t), (pcx + t, pcy), (pcx - t*0.6, pcy + t)], fill=AMBER)
    # glow
    glow = layer.filter(ImageFilter.GaussianBlur(max(1, int(s*0.02))))
    img.paste(glow, (0, 0), glow)
    img.paste(layer, (0, 0), layer)


def large(w, h):
    img = background(w, h)
    d = ImageDraw.Draw(img, "RGBA")
    inset = int(w * 0.05)
    d.rounded_rectangle([inset, inset, w-inset, h-inset], radius=int(w*0.06),
                        outline=DIM, width=max(1, int(w*0.006)))
    draw_icon(img, w*0.5, h*0.30, w*0.44)
    d = ImageDraw.Draw(img, "RGBA")
    # wordmark Hack (green) + On (amber)
    wf = font(int(w*0.15))
    hack, on = "Hack", "On"
    tw = d.textlength(hack, font=wf) + d.textlength(on, font=wf)
    x = w*0.5 - tw/2
    wy = h*0.50
    d.text((x, wy), hack, font=wf, fill=PHOS)
    d.text((x + d.textlength(hack, font=wf), wy), on, font=wf, fill=AMBER)
    # subtitle
    sf = font(int(w*0.052), bold=False)
    ctext(d, w*0.5, h*0.62, "PHOTO & VIDEO", sf, SOFT, spacing=int(w*0.006))
    ctext(d, w*0.5, h*0.67, "DEDUPE", sf, SOFT, spacing=int(w*0.02))
    # bottom prompt
    pf = font(int(w*0.05), bold=False)
    ctext(d, w*0.5, h*0.88, "C:\\> install_", pf, PHOS, spacing=0)
    return img


def small(s):
    img = background(s, s)
    draw_icon(img, s*0.5, s*0.47, s*0.62)
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for w, h in [(164, 314), (246, 459), (328, 604), (410, 797)]:
        large(w, h).save(OUT / f"wizard-large-{w}.png")
    for s in (64, 128):
        small(s).save(OUT / f"wizard-small-{s}.png")
    print("Wrote:", ", ".join(p.name for p in sorted(OUT.glob("wizard-*.png"))))


if __name__ == "__main__":
    main()
