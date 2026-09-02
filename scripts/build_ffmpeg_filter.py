#!/usr/bin/env python3
"""build_ffmpeg_filter.py - Ensambla el filter_complex completo.

decode CUDA -> hwdownload -> crop (si barras) -> split -> bg cover+gblur ->
fg contain -> overlay -> drawtext (unico paso CPU obligatorio) -> NVENC.
"""
import subprocess

import build_background as bb
import build_text_layout as btl


def build(video_path, probe, active, layout, out_path, blur=16.0, cq=21,
          outline=5, wave=2, wave_hz=1.1, font=None, audio=True):
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
    fg = f"[fg]scale={v.w}:{v.h}[fgs];"
    ov = f"[bgb][fgs]overlay={v.x}:{v.y}[base];"
    draws, tmpdir = btl.build_drawtexts(layout, font=font, outline=outline,
                                        wave=wave, wave_hz=wave_hz)
    fc = (pre + bg + fg + ov + "[base]" + ",".join(draws) + "[txt];" +
          "[txt]format=yuv420p[out]")

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
