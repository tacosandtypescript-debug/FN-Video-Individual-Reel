#!/usr/bin/env python3
"""build_background.py - Fondo cover + crop centrado + gblur (regla 5)."""


def cover_dims(src_w, src_h, cw, ch):
    f = max(cw / src_w, ch / src_h)
    sw = int(round(src_w * f))
    sh = int(round(src_h * f))
    if sw % 2:
        sw += 1
    if sh % 2:
        sh += 1
    return sw, sh


def bg_chain(cw, ch, blur):
    return (f"[bg]scale={cw}:{ch}:force_original_aspect_ratio=increase,"
            f"crop={cw}:{ch}:(iw-{cw})/2:(ih-{ch})/2,"
            f"gblur=sigma={blur}[bgb];")
