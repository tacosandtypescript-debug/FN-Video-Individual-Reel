#!/usr/bin/env python3
"""build_ffmpeg_filter.py - Ensambla el filter_complex completo.

decode CUDA -> hwdownload -> crop (si barras) -> split -> bg cover+gblur ->
fg contain -> overlay -> drawtext (unico paso CPU obligatorio) -> NVENC.
"""
import subprocess

import build_background as bb
import build_text_layout as btl


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
          shadow_blur=14, shadow_opacity=0.58):
    v = layout.video
    cw, ch = layout.cw, layout.ch
    cover = bb.cover_dims(active["w"], active["h"], cw, ch)

    is_full = (active["x"] == 0 and active["y"] == 0 and
               active["w"] == probe["width"] and active["h"] == probe["height"])
    if is_full:
        pre = "[0:v]hwdownload,format=nv12[cpu];[cpu]split=2[bg][fg];"
    else:
        pre = (f"[0:v]hwdownload,format=nv12,crop={active['w']}:{active['h']}:"
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
    fc = pre + bg + fg + ov + text_chain + "format=yuv420p[out]"

    cmd = ["ffmpeg", "-y", "-v", "error", "-hwaccel", "cuda",
           "-hwaccel_output_format", "cuda", "-i", video_path,
           "-filter_complex", fc, "-map", "[out]"]
    if audio:
        cmd += ["-map", "0:a?"]
    cmd += ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", str(cq),
            "-pix_fmt", "yuv420p"]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "96k"]
    cmd += ["-shortest", "-movflags", "+faststart", out_path]
    return cmd, tmpdir, cover


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stderr
