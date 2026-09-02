#!/usr/bin/env python3
"""build_text_layout.py - drawtext por linea a partir del layout calculado."""
import os, tempfile


def build_drawtexts(layout, tmpdir=None, font=None, outline=5, wave=2, wave_hz=1.1):
    tmpdir = tmpdir or tempfile.mkdtemp(prefix="vve_text_")
    font = font or layout.font
    draws = []
    all_lines = list(layout.top_block.lines) + list(layout.bot_block.lines)
    for i, ln in enumerate(all_lines):
        tf = os.path.join(tmpdir, f"t{i}.txt")
        with open(tf, "w") as fh:
            fh.write(ln.text)
        xexpr = f"(w-text_w)/2"
        if wave:
            xexpr += f"+{wave}*sin(2*PI*t*{wave_hz})"
        draws.append(
            f"drawtext=fontfile={font}:textfile={tf}:fontsize={ln.size}:"
            f"fontcolor=0x{ln.color}:borderw={outline}:bordercolor=black:"
            f"x='{xexpr}':y={ln.y}")
    return draws, tmpdir
