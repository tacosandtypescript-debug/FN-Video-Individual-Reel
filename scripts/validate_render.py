#!/usr/bin/env python3
"""validate_render.py - Verifica el render sobre pixeles reales y genera frame
de diagnostico (bounding boxes, gaps, safe zones)."""
import argparse
import json
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont
import numpy as np


DURATION_TOLERANCE = 0.1


def validate_output(path, canvas_w, canvas_h):
    """Valida el contrato mínimo del MP4 renderizado antes de medir píxeles."""
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries",
           "stream=width,height,sample_aspect_ratio,display_aspect_ratio,codec_name",
           "-show_entries", "format=duration", "-of", "json", path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("ffprobe de salida falló: " + result.stderr[-500:])
    try:
        data = json.loads(result.stdout)
        video = data["streams"][0]
        width = int(video["width"])
        height = int(video["height"])
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("La salida no contiene un stream de video válido") from exc
    if (width, height) != (canvas_w, canvas_h):
        raise RuntimeError(
            f"Dimensiones de salida inesperadas: {width}x{height}; "
            f"se esperaba {canvas_w}x{canvas_h}"
        )
    if video.get("sample_aspect_ratio") != "1:1":
        raise RuntimeError(
            f"SAR de salida inesperado: {video.get('sample_aspect_ratio')}; se esperaba 1:1"
        )
    if video.get("display_aspect_ratio") != f"{canvas_w}:{canvas_h}":
        # FFprobe simplifica ratios como 1080:1920 a 9:16, por eso se valida
        # también numéricamente para aceptar ambas representaciones.
        dar = video.get("display_aspect_ratio", "")
        try:
            a, b = dar.split(":")
            dar_value = float(a) / float(b)
        except (ValueError, ZeroDivisionError):
            dar_value = 0.0
        if abs(dar_value - canvas_w / canvas_h) > 1e-6:
            raise RuntimeError(f"DAR de salida inesperado: {dar}")
    try:
        duration = float(data.get("format", {}).get("duration", 0))
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        raise RuntimeError("La salida no tiene una duración válida")
    return data


def validate_complete_render(path, canvas_w, canvas_h, expected_duration,
                             tolerance=DURATION_TOLERANCE):
    """Validate the container and ensure the complete source duration survived.

    A valid MP4 can still be truncated while retaining a readable ``moov`` atom.
    The render contract therefore compares the output container duration with
    the duration measured from the source before any frame-level checks.
    """
    data = validate_output(path, canvas_w, canvas_h)
    try:
        actual_duration = float(data.get("format", {}).get("duration", 0))
        expected_duration = float(expected_duration)
        tolerance = max(0.0, float(tolerance))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("No se pudo comparar la duración del render") from exc
    if expected_duration <= 0:
        raise RuntimeError("La duración esperada del video no es válida")
    if abs(actual_duration - expected_duration) > tolerance:
        raise RuntimeError(
            f"Render incompleto: duración {actual_duration:.3f}s; "
            f"se esperaban {expected_duration:.3f}s (tolerancia {tolerance:.3f}s)"
        )
    return data


def extract_frame(path, t, out):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", path,
                    "-frames:v", "1", out], check=True)
    if not os.path.isfile(out) or os.path.getsize(out) == 0:
        raise RuntimeError(f"FFmpeg no generó el frame de validación: {out}")


def _color_mask(a, hexc, tol=30):
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    hx = hexc.lstrip("#")
    r = int(hx[0:2], 16); g = int(hx[2:4], 16); b = int(hx[4:6], 16)
    return (abs(R - r) <= tol) & (abs(G - g) <= tol) & (abs(B - b) <= tol)


def _line_color_mask(a, line):
    """Máscara de todos los colores visibles de una línea segmentada."""
    colors = {color for _, color in (line.segments or [(line.text, line.color)])}
    mask = np.zeros(a.shape[:2], dtype=bool)
    for color in colors:
        mask |= _color_mask(a, color)
    return mask


def measure_gaps(frame_png, layout, anchor_top=None, anchor_bottom=None):
    """Mide gaps reales usando VENTANAS alrededor del modelo (los glifos estan
    donde el layout dice, ±pocos px) y umbral proporcional al ancho de la linea
    ancla. Devuelve (gap_top_real, gap_bot_real)."""
    im = Image.open(frame_png).convert("RGB")
    a = np.asarray(im).astype(int)
    v = layout.video
    cw = layout.cw
    gtop = gbot = None

    # --- gap superior: ancla = ultima linea del bloque superior ---
    if anchor_top and layout.top_block.lines:
        ln = layout.top_block.lines[-1]
        thr = max(12, int(ln.width_px * 0.06))
        half = max(ln.width_px // 2 + 40, 100)
        x0 = max(0, cw // 2 - half)
        x1 = min(cw, cw // 2 + half)
        y0 = max(0, ln.y - 4)
        y1 = min(v.top - 1, ln.y + layout.top_block.bottom - ln.y + 6)
        sl = _line_color_mask(a, ln)[y0:y1, x0:x1]
        rows = np.where(sl.sum(axis=1) >= thr)[0]
        if len(rows):
            gtop = v.top - (int(rows.max()) + y0)

    # --- gap inferior: ancla = primera linea del bloque inferior ---
    if anchor_bottom and layout.bot_block.lines:
        ln = layout.bot_block.lines[0]
        thr = max(12, int(ln.width_px * 0.06))
        half = max(ln.width_px // 2 + 40, 100)
        x0 = max(0, cw // 2 - half)
        x1 = min(cw, cw // 2 + half)
        y0 = max(v.bottom + 1, ln.y - 6)
        y1 = min(layout.ch, ln.y + layout.bot_block.bottom - ln.y + 4)
        sl = _line_color_mask(a, ln)[y0:y1, x0:x1]
        rows = np.where(sl.sum(axis=1) >= thr)[0]
        if len(rows):
            gbot = (int(rows.min()) + y0) - v.bottom
    return gtop, gbot


def diagnostic_frame(source_png, layout, out_png):
    im = Image.open(source_png).convert("RGB")
    d = ImageDraw.Draw(im)
    v = layout.video
    sl = layout.safe_limits
    w, h = im.size
    f = max(1, int(w / 60))
    try:
        ft = ImageFont.truetype(layout.font, f)
    except Exception:
        ft = ImageFont.load_default()
    d.rectangle([sl["left"], sl["top"], sl["right"], sl["bottom"]], outline=(255, 255, 0), width=2)
    d.rectangle([v.x, v.top, v.right, v.bottom], outline=(0, 255, 255), width=3)
    for blk, col in ((layout.top_block, (0, 255, 0)), (layout.bot_block, (255, 0, 255))):
        if not blk.lines:
            continue
        d.rectangle([blk.left, blk.top, blk.right, blk.bottom], outline=col, width=2)
        gap = layout.gap_top if col == (0, 255, 0) else layout.gap_bot
        d.text((blk.left + 2, blk.top - f - 2), f"gap {gap}", fill=col, font=ft)
    d.text((10, 10), f"videoTop={v.top} videoBottom={v.bottom}", fill=(0, 255, 255), font=ft)
    im.save(out_png)
    return out_png


def main():
    parser = argparse.ArgumentParser(
        description="Valida dimensiones, SAR, DAR y duración de un MP4 vertical"
    )
    parser.add_argument("video")
    parser.add_argument("--canvas", default="1080x1920")
    parser.add_argument(
        "--expected-duration", type=float, default=None,
        help="duración esperada en segundos; si se omite solo valida el contenedor",
    )
    args = parser.parse_args()
    try:
        canvas_w, canvas_h = (int(value) for value in args.canvas.lower().split("x"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise SystemExit("--canvas debe tener el formato WxH") from exc
    if (canvas_w <= 0 or canvas_h <= 0 or canvas_w * 16 != canvas_h * 9):
        raise SystemExit("--canvas debe ser un tamaño vertical 9:16 válido")
    try:
        if args.expected_duration is None:
            data = validate_output(args.video, canvas_w, canvas_h)
        else:
            data = validate_complete_render(
                args.video, canvas_w, canvas_h, args.expected_duration
            )
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
    print(json.dumps(data, ensure_ascii=False))
    print("VALID: render compatible con el contrato solicitado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
