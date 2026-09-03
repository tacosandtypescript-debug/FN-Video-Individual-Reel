#!/usr/bin/env python3
"""build_text_layout.py - drawtext por linea a partir del layout calculado."""
import os, tempfile


def build_drawtexts(layout, tmpdir=None, font=None, outline=5, wave=2, wave_hz=1.1):
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
        from PIL import ImageFont
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
            with open(tf, "w") as fh:
                fh.write(text)
            xexpr = xbase if offset == 0 else f"{xbase}+{offset}"
            if wave:
                xexpr += f"+{wave}*sin(2*PI*t*{wave_hz})"
            draws.append(
                f"drawtext=fontfile={font}:textfile={tf}:fontsize={ln.size}:"
                f"fontcolor=0x{color}:borderw={outline}:bordercolor=black:"
                f"x='{xexpr}':y={segment_y}")
            offset += width
    return draws, tmpdir
