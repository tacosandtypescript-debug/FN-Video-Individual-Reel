#!/usr/bin/env python3
"""build_ffmpeg_filter.py - Ensambla el filter_complex completo.

decode CUDA -> hwdownload -> crop (si barras) -> split -> bg cover+gblur ->
fg contain -> overlay -> drawtext (unico paso CPU obligatorio) -> NVENC/libx264.
"""
import shutil
import subprocess

import build_background as bb
import build_text_layout as btl


def cuda_available():
    """Comprueba de forma barata si hay un driver NVIDIA utilizable."""
    if not shutil.which("nvidia-smi"):
        return False
    try:
        result = subprocess.run(["nvidia-smi", "-L"], capture_output=True,
                                text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0 or not result.stdout.strip():
        return False
    try:
        encoders = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                                  capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return encoders.returncode == 0 and "h264_nvenc" in (encoders.stdout + encoders.stderr)


def _video_encode_args(encode, cq, use_cuda):
    """Construye flags coherentes para NVENC o para el fallback libx264."""
    requested = encode.get("vcodec", "h264_nvenc")
    vcodec = requested
    if requested.endswith("_nvenc") and not use_cuda:
        vcodec = encode.get("cpu_vcodec", "libx264")
    args = ["-c:v", vcodec]
    if vcodec.endswith("_nvenc"):
        args += ["-preset", str(encode.get("preset", "p5")),
                 "-cq", str(cq)]
    elif vcodec == "libx264":
        args += ["-preset", str(encode.get("cpu_preset", "medium")),
                 "-crf", str(cq)]
    else:
        args += ["-preset", str(encode.get("preset", "medium"))]
    return args


def _rounded_alpha_expr(w, h, r):
    """Máscara compacta: mantiene el rectángulo y recorta sus cuatro esquinas."""
    # Distancia al centro: el rectángulo interior queda opaco; las esquinas
    # exteriores de radio r quedan transparentes.
    return (f"if(lt(X,{r})*lt(Y,{r})*gt((X-{r})*(X-{r})+(Y-{r})*(Y-{r}),{r*r})\\,0\\,"
            f"if(lt(X,{r})*gt(Y,{h-r})*gt((X-{r})*(X-{r})+(Y-{h-r})*(Y-{h-r}),{r*r})\\,0\\,"
            f"if(gt(X,{w-r})*lt(Y,{r})*gt((X-{w-r})*(X-{w-r})+(Y-{r})*(Y-{r}),{r*r})\\,0\\,"
            f"if(gt(X,{w-r})*gt(Y,{h-r})*gt((X-{w-r})*(X-{w-r})+(Y-{h-r})*(Y-{h-r}),{r*r})\\,0\\,255))))")


def build(video_path, probe, active, layout, out_path, blur=16.0, cq=21,
          outline=5, wave=2, wave_hz=1.1, font=None, audio=True,
          fg_radius=18, shadow_enabled=True, shadow_offset=8,
          shadow_blur=14, shadow_opacity=0.58, encode=None, use_cuda=None):
    encode = encode or {}
    requested_vcodec = encode.get("vcodec", "h264_nvenc")
    if use_cuda is None:
        use_cuda = requested_vcodec.endswith("_nvenc")
    v = layout.video
    cw, ch = layout.cw, layout.ch
    cover = bb.cover_dims(active["w"], active["h"], cw, ch)

    is_full = (active["x"] == 0 and active["y"] == 0 and
               active["w"] == probe["width"] and active["h"] == probe["height"])
    if is_full:
        decode = "hwdownload,"
        pre = f"[0:v]{decode if use_cuda else ''}format=nv12[cpu];[cpu]split=2[bg][fg];"
    else:
        decode = "hwdownload," if use_cuda else ""
        pre = (f"[0:v]{decode}format=nv12,crop={active['w']}:{active['h']}:"
               f"{active['x']}:{active['y']},format=nv12,split=2[bg][fg];")

    bg = bb.bg_chain(cw, ch, blur)
    fg = f"[fg]scale={v.w}:{v.h},format=rgba[fgs];"
    mask_expr = _rounded_alpha_expr(v.w, v.h, max(2, fg_radius))
    mask = (f"color=c=white:s={v.w}x{v.h}:r=60,format=gray,"
            f"geq=lum='255':a='{mask_expr}'[mask];")
    rounded = "[mask]split=2[maskfg][maskshadow];[fgs][maskfg]alphamerge[fgra];"
    if shadow_enabled:
        shadow = (f"[maskshadow]boxblur=luma_radius={shadow_blur}:luma_power=1,"
                  f"geq=lum='lum(X,Y)*{shadow_opacity}'[smask];"
                  f"color=c=black:s={v.w}x{v.h}:r=60,format=rgba[sc];"
                  f"[sc][smask]alphamerge[shadow];")
        ov = (f"[bgb][shadow]overlay={v.x + shadow_offset}:{v.y + shadow_offset}:"
              f"shortest=1[shadowbase];[shadowbase][fgra]overlay={v.x}:{v.y}:shortest=1[base];")
    else:
        shadow = ""
        ov = f"[bgb][fgra]overlay={v.x}:{v.y}:shortest=1[base];"
    fg = fg + mask + rounded + shadow
    draws, tmpdir = btl.build_drawtexts(layout, font=font, outline=outline,
                                        wave=wave, wave_hz=wave_hz)
    if draws:
        text_chain = "[base]" + ",".join(draws) + "[txt];[txt]"
    else:
        text_chain = "[base]"
    pix_fmt = encode.get("pix_fmt", "yuv420p")
    fc = pre + bg + fg + ov + text_chain + f"format={pix_fmt},setsar=1[out]"

    cmd = ["ffmpeg", "-y", "-v", "error"]
    if use_cuda:
        cmd += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
    cmd += ["-i", video_path, "-filter_complex", fc, "-map", "[out]"]
    if audio:
        cmd += ["-map", "0:a?"]
    cmd += _video_encode_args(encode, cq, use_cuda)
    cmd += ["-pix_fmt", pix_fmt]
    if audio:
        cmd += ["-c:a", str(encode.get("acodec", "aac")),
                "-b:a", str(encode.get("audio_bitrate", "96k"))]
    cmd += ["-shortest", "-movflags", "+faststart", out_path]
    return cmd, tmpdir, cover


def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired as exc:
        return 124, "ffmpeg agotó el timeout de 3600 segundos: " + str(exc)
    return r.returncode, r.stderr
