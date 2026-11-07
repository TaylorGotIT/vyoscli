#!/usr/bin/env python3
"""vyoscli icon: OpenWrt-blue square + VyOS-colored CLI circle."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent.parent / "docs" / "assets"
OUT.mkdir(parents=True, exist_ok=True)
S = 1024
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_MONO = "C:/Windows/Fonts/consolab.ttf"

# OpenWrt theme blue and VyOS dark navy/cyan
OWRT_TOP = (0, 180, 226)
OWRT_BOTTOM = (0, 143, 191)
VYOS_TOP = (12, 31, 58)
VYOS_BOTTOM = (15, 43, 74)
CYAN = (34, 211, 238)


def main() -> None:
    y, x = np.mgrid[0:S, 0:S]
    t = (x + y) / (2 * S)
    top = np.array(OWRT_TOP, dtype=float)
    bottom = np.array(OWRT_BOTTOM, dtype=float)
    arr = top[None, None, :] * (1 - t[..., None]) + bottom[None, None, :] * t[..., None]
    img = Image.fromarray(arr.astype("uint8"), "RGB").convert("RGBA")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((24, 24, S - 24, S - 24),
                                           radius=220, fill=255)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    d = ImageDraw.Draw(out)

    # OpenWrt wordmark in the square
    d.text((512, 190), "openwrt", font=ImageFont.truetype(FONT_BOLD, 88),
           fill=(255, 255, 255, 255), anchor="mm")

    # VyOS-colored circle: the CLI layer
    cx, cy, r = 512, 620, 300
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((cx - r, cy - r + 20, cx + r, cy + r + 20),
                                   fill=(0, 30, 55, 120))
    out.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(24)))
    # vertical gradient inside the circle
    gy0, gy1 = cy - r, cy + r
    circle = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    cd = ImageDraw.Draw(circle)
    for yy in range(gy0, gy1 + 1):
        f = (yy - gy0) / max(1, gy1 - gy0)
        color = tuple(int(VYOS_TOP[i] * (1 - f) + VYOS_BOTTOM[i] * f) for i in range(3))
        cd.line([(cx - r, yy), (cx + r, yy)], fill=color + (255,))
    circle_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(circle_mask).ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    out.paste(circle, (0, 0), circle_mask)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=CYAN + (230,), width=7)

    # terminal prompt >_
    mono = ImageFont.truetype(FONT_MONO, 250)
    gw = d.textlength(">", font=mono)
    cursor_w, cursor_h = 100, 24
    total = gw + 28 + cursor_w
    x0 = cx - total / 2
    baseline = cy + 10
    d.text((x0, baseline), ">", font=mono, fill=(255, 255, 255, 255), anchor="ls")
    d.rounded_rectangle((x0 + gw + 28, baseline - cursor_h,
                         x0 + gw + 28 + cursor_w, baseline),
                        radius=5, fill=CYAN + (255,))

    # vyoscli wordmark
    wf = ImageFont.truetype(FONT_BOLD, 82)
    vw = d.textlength("vyos", font=wf)
    cw = d.textlength("cli", font=wf)
    sx = cx - (vw + cw) / 2
    d.text((sx, 760), "vyos", font=wf, fill=(255, 255, 255, 255))
    d.text((sx + vw, 760), "cli", font=wf, fill=CYAN + (255,))

    # outer frame
    d.rounded_rectangle((24, 24, S - 24, S - 24), radius=220,
                        outline=(255, 255, 255, 40), width=4)

    out.save(OUT / "vyoscli-icon.png")
    for size in (512, 256):
        out.resize((size, size), Image.LANCZOS).save(OUT / f"vyoscli-icon-{size}.png")
    print("wrote", OUT / "vyoscli-icon.png")


if __name__ == "__main__":
    main()
