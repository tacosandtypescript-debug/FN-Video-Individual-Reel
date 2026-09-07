#!/usr/bin/env python3
"""build_text_layout.py - drawtext por línea y firma del preset."""
import os
import re
import tempfile
import unicodedata

from PIL import ImageFont


def _filter_escape(value):
    """Escape a filesystem value used inside a quoted FFmpeg option."""
    return (str(value).replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace(":", "\\:"))


def build_drawtexts(layout, tmpdir=None, font=None, outline=5, outline_color="black",
                    wave=2, wave_hz=1.1):
    tmpdir = tmpdir or tempfile.mkdtemp(prefix="vve_text_")
    font = font or layout.font
    draws = []
    all_lines = list(layout.top_block.lines) + list(layout.bot_block.lines)
    for i, ln in enumerate(all_lines):
        # Una línea puede contener segmentos {PALABRA|RRGGBB}. Se miden como
        # conjunto en calculate_layout y se colocan consecutivos, centrados como
        # una sola frase (no como líneas independientes).
        segments = ln.segments or [(ln.text, ln.color)]
        widths = []
        ff = ImageFont.truetype(font, ln.size)
        widths = [int(round(ff.getlength(text))) for text, _ in segments]
        # drawtext posiciona cada segmento desde su borde superior. Para que
        # palabras con alturas de glifo distintas (p. ej. MAÑANA / FORTNITE)
        # compartan baseline visual, se alinea su borde inferior al bbox de la
        # línea completa.
        heights = [max(1, ff.getbbox(text)[3] - ff.getbbox(text)[1]) for text, _ in segments]
        xbase = f"(w-{sum(widths)})/2"
        offset = 0
        for j, ((text, color), width) in enumerate(zip(segments, widths)):
            segment_y = ln.y + max(0, ln.height_px - heights[j])
            tf = os.path.join(tmpdir, f"t{i}_{j}.txt")
            with open(tf, "w", encoding="utf-8") as fh:
                fh.write(text)
            xexpr = xbase if offset == 0 else f"{xbase}+{offset}"
            if wave:
                xexpr += f"+{wave}*sin(2*PI*t*{wave_hz})"
            draws.append(
                f"drawtext=fontfile='{_filter_escape(font)}':"
                f"textfile='{_filter_escape(tf)}':fontsize={ln.size}:"
                f"fontcolor=0x{color}:borderw={outline}:"
                f"bordercolor={outline_color}:"
                f"x='{xexpr}':y={segment_y}")
            offset += width
    return draws, tmpdir


def build_watermark_drawtext(text, font, font_size, tmpdir, y, color="FFFFFF",
                             alpha=0.82, outline=2, outline_color="black"):
    """Build a centered, standalone text-only watermark filter."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    ).upper()
    if not text:
        return None
    color = str(color).lstrip("#").upper()
    if len(color) != 6 or any(ch not in "0123456789ABCDEF" for ch in color):
        raise ValueError(f"Color de watermark inválido: {color}")
    try:
        alpha = max(0.0, min(1.0, float(alpha)))
    except (TypeError, ValueError) as exc:
        raise ValueError("La opacidad del watermark debe estar entre 0 y 1") from exc
    os.makedirs(tmpdir, exist_ok=True)
    text_path = os.path.join(tmpdir, "watermark.txt")
    with open(text_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return (
        f"drawtext=fontfile='{_filter_escape(font)}':"
        f"textfile='{_filter_escape(text_path)}':fontsize={max(1, int(font_size))}:"
        f"fontcolor=0x{color}@{alpha:g}:borderw={max(0, int(outline))}:"
        f"bordercolor={outline_color}:x='(w-text_w)/2':y={max(0, int(y))}"
    )
