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


def cover_crop_dims(src_w, src_h, cw, ch):
    """Return an even-sized centered crop with the canvas aspect ratio."""
    if min(src_w, src_h, cw, ch) <= 0:
        raise ValueError("Las dimensiones del cover deben ser positivas")
    if src_w * ch > src_h * cw:
        crop_w = max(2, int(round(src_h * cw / ch)))
        crop_w -= crop_w % 2
        crop_h = src_h - (src_h % 2)
    else:
        crop_w = src_w - (src_w % 2)
        crop_h = max(2, int(src_w * ch / cw))
        crop_h -= crop_h % 2
    return crop_w, crop_h


def bg_chain(cw, ch, blur, *, src_w=None, src_h=None, mode="scale-crop"):
    if mode == "precrop":
        if src_w is None or src_h is None:
            raise ValueError("precrop necesita las dimensiones de la fuente")
        crop_w, crop_h = cover_crop_dims(src_w, src_h, cw, ch)
        return (f"[bg]crop={crop_w}:{crop_h}:(iw-{crop_w})/2:(ih-{crop_h})/2,"
                f"scale={cw}:{ch},gblur=sigma={blur}[bgb];")
    if mode != "scale-crop":
        raise ValueError(f"Modo de cover inválido: {mode}")
    return (f"[bg]scale={cw}:{ch}:force_original_aspect_ratio=increase,"
            f"crop={cw}:{ch}:(iw-{cw})/2:(ih-{ch})/2,"
            f"gblur=sigma={blur}[bgb];")
