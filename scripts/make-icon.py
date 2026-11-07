#!/usr/bin/env python3
"""Generate the minimal vyoscli icon: OpenWrt base + terminal prompt."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent.parent / "docs" / "assets"
OUT.mkdir(parents=True, exist_ok=True)
S = 1024
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_MONO = "C:/Windows/Fonts/consolab.ttf"


def main() -> None:
    # dark rounded background
    y, x = np.mgrid[0:S, 0:S]
    t = (x + y) / (2 * S)
    top = np.array([6, 19, 33], dtype=float)
    bottom = np.array([9, 39, 61], dtype=float)
    arr = top[None, None, :] * (1 - t[..., None]) + bottom[None, None, :] * t[..., None]
    img = Image.fromarray(arr.astype("uint8"), "RGB").convert("RGBA")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((24, 24, S - 24, S - 24),
                                           radius=220, fill=255)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    d = ImageDraw.Draw(out)

    # OpenWrt foundation circle
    cx, cy, r = 512, 520, 318
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((cx - r, cy - r + 22, cx + r, cy + r + 22),
                                   fill=(0, 0, 0, 135))
    out.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(26)))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(9, 79, 132, 255))
    d.ellipse((cx - r + 8, cy - r + 8, cx + r - 8, cy + r - 8),
              fill=(8, 66, 110, 255))
    d.ellipse((cx - r, cy - r, cx + r, cy + r),
              outline=(34, 211, 238, 220), width=7)

    # terminal prompt >_
    mono = ImageFont.truetype(FONT_MONO, 300)
    gt = ">"
    gw = d.textlength(gt, font=mono)
    cursor_w, cursor_h = 118, 26
    total = gw + 34 + cursor_w
    x0 = cx - total / 2
    baseline = cy - 20
    d.text((x0, baseline), gt, font=mono, fill=(245, 250, 255, 255), anchor="ls")
    d.rounded_rectangle((x0 + gw + 34, baseline - cursor_h,
                         x0 + gw + 34 + cursor_w, baseline),
                        radius=5, fill=(34, 211, 238, 255))

    # wordmark inside the base
    wf = ImageFont.truetype(FONT_BOLD, 92)
    vy = "vyos"
    vw = d.textlength(vy, font=wf)
    cw = d.textlength("cli", font=wf)
    sx = cx - (vw + cw) / 2
    d.text((sx, 650), vy, font=wf, fill=(245, 250, 255, 255))
    d.text((sx + vw, 650), "cli", font=wf, fill=(34, 211, 238, 255))

    # outer border
    d.rounded_rectangle((24, 24, S - 24, S - 24), radius=220,
                        outline=(45, 110, 140, 210), width=4)

    out.save(OUT / "vyoscli-icon.png")
    for size in (512, 256):
        out.resize((size, size), Image.LANCZOS).save(OUT / f"vyoscli-icon-{size}.png")
    print("wrote", OUT / "vyoscli-icon.png")


if __name__ == "__main__":
    main()
