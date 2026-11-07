#!/usr/bin/env python3
"""Generate the vyoscli project icon (OpenWrt base + VyOS-style CLI)."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent.parent / "docs" / "assets"
OUT.mkdir(parents=True, exist_ok=True)

S = 1024
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_REG = "C:/Windows/Fonts/segoeui.ttf"
FONT_MONO = "C:/Windows/Fonts/consola.ttf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((24, 24, size - 24, size - 24), radius=radius, fill=255)
    return mask


def background() -> Image.Image:
    y, x = np.mgrid[0:S, 0:S]
    t = (x + y) / (2 * S)
    top = np.array([7, 22, 38], dtype=float)
    bottom = np.array([10, 47, 74], dtype=float)
    arr = top[None, None, :] * (1 - t[..., None]) + bottom[None, None, :] * t[..., None]
    img = Image.fromarray(arr.astype("uint8"), "RGB").convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    for p in range(48, S, 64):
        d.line([(p, 0), (p, S)], fill=(120, 200, 230, 10), width=1)
        d.line([(0, p), (S, p)], fill=(120, 200, 230, 10), width=1)
    # top glow
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-180, -420, S + 180, 260), fill=(34, 211, 238, 28))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(80)))
    return img


def draw_centered(d, xy, text, fnt, fill):
    d.text(xy, text, font=fnt, fill=fill, anchor="mm")


def main() -> None:
    img = background()
    d = ImageDraw.Draw(img, "RGBA")

    # OpenWrt base: big blue foundation circle behind the terminal.
    cx, cy, r = 512, 760, 238
    d.ellipse((cx - r - 18, cy - r - 18, cx + r + 18, cy + r + 18),
              outline=(0, 166, 214, 65), width=3)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(10, 84, 138, 255))
    d.ellipse((cx - r + 10, cy - r + 10, cx + r - 10, cy + r - 10),
              fill=(8, 64, 108, 255))
    # subtle orbit
    d.arc((cx - 270, cy - 270, cx + 270, cy + 270), 200, 340,
          fill=(34, 211, 238, 150), width=4)
    draw_centered(d, (cx, cy + 88), "openwrt", font(FONT_BOLD, 64), (240, 250, 255, 255))
    # letter-spaced BASE label
    bx = cx - 46
    for ch in "BASE":
        d.text((bx, cy + 140), ch, font=font(FONT_BOLD, 19), fill=(105, 224, 255, 235))
        bx += 24

    # Terminal window.
    x0, y0, x1, y1 = 180, 330, 844, 670
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((x0 + 10, y0 + 24, x1 + 10, y1 + 24),
                                             radius=30, fill=(0, 0, 0, 130))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(24)))

    d.rounded_rectangle((x0, y0, x1, y1), radius=28, fill=(8, 15, 26, 255),
                        outline=(42, 74, 94, 255), width=3)
    d.rounded_rectangle((x0, y0, x1, y0 + 54), radius=28, fill=(14, 27, 42, 255))
    d.rectangle((x0, y0 + 34, x1, y0 + 54), fill=(14, 27, 42, 255))
    d.line((x0, y0 + 54, x1, y0 + 54), fill=(36, 62, 80, 255), width=2)

    for i, color in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        d.ellipse((x0 + 22 + i * 24, y0 + 19, x0 + 38 + i * 24, y0 + 35), fill=color)

    # VyOS-style V mark in the title bar.
    d.polygon([(230, y0 + 17), (243, y0 + 17), (256, y0 + 35), (243, y0 + 35)],
              fill=(34, 211, 238, 255))
    d.polygon([(256, y0 + 35), (269, y0 + 35), (282, y0 + 17), (269, y0 + 17)],
              fill=(34, 211, 238, 255))
    d.text((300, y0 + 17), "vyoscli", font=font(FONT_BOLD, 24),
           fill=(196, 214, 228, 255))

    mono = font(FONT_MONO, 25)
    x = x0 + 40
    rows = [
        (y0 + 96, "root@openwrt:~$", (125, 147, 168), " configure", (232, 241, 248)),
        (y0 + 144, "root@openwrt#", (61, 220, 151), " commit", (232, 241, 248)),
        (y0 + 192, "", (0, 0, 0), "OK  configuration applied", (61, 220, 151)),
        (y0 + 240, "", (0, 0, 0), "vyoscli>", (34, 211, 238)),
    ]
    for yy, left, lc, right, rc in rows:
        if left:
            d.text((x, yy), left, font=mono, fill=lc)
            lw = d.textlength(left, font=mono)
            d.text((x + lw, yy), right, font=mono, fill=rc)
        else:
            d.text((x, yy), right, font=mono, fill=rc)
    # cursor after last prompt
    last_w = d.textlength("vyoscli>", font=mono)
    d.rectangle((x + last_w + 6, y0 + 236, x + last_w + 20, y0 + 264),
                fill=(34, 211, 238, 210))

    # Wordmark.
    draw_centered(d, (512, 90), "V Y O S - S T Y L E   C L I",
                  font(FONT_BOLD, 21), (105, 224, 255, 235))
    vy_f = font(FONT_BOLD, 112)
    vy_w = d.textlength("vyos", font=vy_f)
    cli_w = d.textlength("cli", font=vy_f)
    total = vy_w + cli_w
    start = 512 - total / 2
    d.text((start, 116), "vyos", font=vy_f, fill=(245, 250, 255, 255))
    d.text((start + vy_w, 116), "cli", font=vy_f, fill=(34, 211, 238, 255))
    draw_centered(d, (512, 268), "VyOS-style CLI for OpenWrt",
                  font(FONT_REG, 33), (154, 178, 198, 255))

    # Outer rounded frame + subtle inner highlight.
    mask = rounded_mask(S, 210)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    od = ImageDraw.Draw(out)
    od.rounded_rectangle((24, 24, S - 24, S - 24), radius=210,
                         outline=(60, 130, 160, 200), width=4)
    od.rounded_rectangle((40, 40, S - 40, S - 40), radius=196,
                         outline=(120, 220, 240, 28), width=1)

    out.save(OUT / "vyoscli-icon.png")
    for size in (512, 256):
        out.resize((size, size), Image.LANCZOS).save(OUT / f"vyoscli-icon-{size}.png")
    print("wrote", OUT / "vyoscli-icon.png")


if __name__ == "__main__":
    main()
