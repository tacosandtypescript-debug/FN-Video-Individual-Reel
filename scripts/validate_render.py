#!/usr/bin/env python3
"""validate_render.py - Verifica el render sobre pixeles reales y genera frame
de diagnostico (bounding boxes, gaps, safe zones)."""
import subprocess

from PIL import Image, ImageDraw, ImageFont
import numpy as np


def extract_frame(path, t, out):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", path,
                    "-frames:v", "1", out], check=True)


def measure_gaps(frame_png, layout, anchor_bot, anchor_top):
    """Mide gaps reales. Devuelve (gap_top_real, gap_bot_real)."""
    im = Image.open(frame_png).convert("RGB")
    a = np.asarray(im).astype(int)
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    v = layout.video
    cw = layout.cw

    def color_mask(hexc, tol=30):
        hx = hexc.lstrip("#")
        r = int(hx[0:2], 16); g = int(hx[2:4], 16); b = int(hx[4:6], 16)
        return (abs(R - r) <= tol) & (abs(G - g) <= tol) & (abs(B - b) <= tol)

    def find_rows(hexc, y0, y1, half):
        x0 = max(0, cw // 2 - half)
        x1 = min(cw, cw // 2 + half)
        sl = color_mask(hexc)[y0:y1, x0:x1]
        strong = np.where(sl.sum(axis=1) >= 40)[0]
        if len(strong) == 0:
            return None
        return (int(strong.min()) + y0, int(strong.max()) + y0)

    allw = [ln.width_px for ln in list(layout.top_block.lines) + list(layout.bot_block.lines)]
    half = max(allw or [300]) // 2 + 40
    gtop = gbot = None
    if anchor_bot:
        rs = find_rows(anchor_bot, 0, max(0, v.top - 1), half)
        gtop = v.top - rs[1] if rs else None
    if anchor_top:
        rs = find_rows(anchor_top, min(v.bottom + 1, layout.ch), layout.ch, half)
        gbot = rs[0] - v.bottom if rs else None
    return gtop, gbot


def diagnostic_frame(source_png, layout, out_png):
    """Dibuja bbox de video/bloques, gaps y safe zones sobre el frame."""
    im = Image.open(source_png).convert("RGB")
    d = ImageDraw.Draw(im)
    v = layout.video
    sl = layout.safe_limits
    w, h = im.size
    f = max(1, int(w / 60))
    try:
        ft = ImageFont.truetype("/home/isaac/.local/share/fonts/Barlow-ExtraBoldItalic.ttf", f)
    except Exception:
        ft = ImageFont.load_default()
    d.rectangle([sl["left"], sl["top"], sl["right"], sl["bottom"]], outline=(255, 255, 0), width=2)
    d.rectangle([v.x, v.top, v.right, v.bottom], outline=(0, 255, 255), width=3)
    for blk, col in ((layout.top_block, (0, 255, 0)), (layout.bot_block, (255, 0, 255))):
        d.rectangle([blk.left, blk.top, blk.right, blk.bottom], outline=col, width=2)
        gap = layout.gap_top if col == (0, 255, 0) else layout.gap_bot
        d.text((blk.left + 2, blk.top - f - 2), f"gap {gap}", fill=col, font=ft)
    d.text((10, 10), f"videoTop={v.top} videoBottom={v.bottom}", fill=(0, 255, 255), font=ft)
    im.save(out_png)
    return out_png
