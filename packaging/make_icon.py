# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""Draw the JAF Rule Bench icon and write packaging/jaf.ico (16 to 256 px) and packaging/jaf_icon.png.

Design: the same flat rounded square as the A-share Company Intelligence icon, in the Rule Bench indigo.
A digital-asset token (a diamond) on the left is assigned by a bold line to one of three jurisdictions on
the right (the filled one); thin lines to the two others are the competing claims the rule resolves.
Small sizes drop the thin lines so the mark stays legible at 16 px.
Usage: python packaging/make_icon.py   (needs Pillow; run once, the outputs are committed)
"""
import os
from PIL import Image, ImageDraw

BG = (58, 47, 214, 255)        # --accent #3a2fd6
FG = (255, 255, 255, 255)
SOFT = tuple(round(b + 0.62 * (255 - b)) for b in BG[:3]) + (255,)   # white at 62% over indigo, opaque
HERE = os.path.dirname(os.path.abspath(__file__))


def draw(size, detail=True):
    S = 1024                                            # draw large, then downsample
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pad = 24 if size >= 48 else 8
    d.rounded_rectangle([pad, pad, S - pad, S - pad], radius=190, fill=BG)
    tok = (330, 512)                                     # token centre
    nodes = [(745, 270), (745, 512), (745, 754)]
    if detail:
        for n in (nodes[0], nodes[2]):                   # competing claims
            d.line([tok, n], fill=SOFT, width=34)
    d.line([tok, nodes[1]], fill=FG, width=86 if detail else 120)
    r = 175 if detail else 200                           # diamond half-diagonal
    d.polygon([(tok[0] - r, tok[1]), (tok[0], tok[1] - r), (tok[0] + r, tok[1]), (tok[0], tok[1] + r)], fill=FG)
    rr = 92 if detail else 120
    d.ellipse([nodes[1][0] - rr, nodes[1][1] - rr, nodes[1][0] + rr, nodes[1][1] + rr], fill=FG)
    if detail:                                           # unassigned jurisdictions: rings
        for n in (nodes[0], nodes[2]):
            d.ellipse([n[0] - 78, n[1] - 78, n[0] + 78, n[1] + 78], fill=BG, outline=FG, width=34)
    else:
        for n in (nodes[0], nodes[2]):
            d.ellipse([n[0] - 80, n[1] - 80, n[0] + 80, n[1] + 80], fill=SOFT)
    return im.resize((size, size), Image.LANCZOS)


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [draw(s, detail=s >= 48) for s in sizes]
    frames[-1].save(os.path.join(HERE, "jaf.ico"), sizes=[(s, s) for s in sizes], append_images=frames[:-1])
    draw(512).save(os.path.join(HERE, "jaf_icon.png"))
    print("wrote jaf.ico and jaf_icon.png")


if __name__ == "__main__":
    main()
