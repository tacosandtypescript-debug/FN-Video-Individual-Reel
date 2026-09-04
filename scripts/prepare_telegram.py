#!/usr/bin/env python3
"""Prepara un MP4 vertical para Telegram.

Conserva el archivo si ya está por debajo del límite práctico. Si pesa demasiado,
crea una copia 720x1280 con SAR 1:1, DAR 9:16 y encode NVENC.
"""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

MAX_BYTES = 45 * 1024 * 1024

def probe(path):
    cmd = ["ffprobe", "-v", "error", "-show_entries",
           "stream=width,height,sample_aspect_ratio,display_aspect_ratio,codec_type",
           "-show_entries", "format=size,duration", "-of", "json", path]
    return json.loads(subprocess.check_output(cmd, text=True))

def run(cmd):
    subprocess.run(cmd, check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--max-mb", type=float, default=45)
    a = ap.parse_args()
    src = Path(a.input); dst = Path(a.output); dst.parent.mkdir(parents=True, exist_ok=True)
    limit = int(a.max_mb * 1024 * 1024)
    source_info = probe(str(src)); source_streams = source_info.get("streams", [])
    source_video = next(s for s in source_streams if s.get("codec_type") == "video")
    source_sar_ok = source_video.get("sample_aspect_ratio") == "1:1"
    source_dar_ok = source_video.get("width", 0) * 16 == source_video.get("height", 0) * 9
    if src.stat().st_size <= limit and source_sar_ok and source_dar_ok:
        if src.resolve() != dst.resolve(): shutil.copy2(src, dst)
        mode = "copied"
    else:
        run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
             "-vf", "scale=720:1280:force_original_aspect_ratio=decrease:flags=lanczos,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1",
             "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "23", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(dst)])
        mode = "reencoded"
    info = probe(str(dst)); streams = info.get("streams", []); video = next(s for s in streams if s.get("codec_type") == "video")
    if video.get("width") / video.get("height") != 0.5625:
        raise RuntimeError("La salida no es 9:16")
    if video.get("sample_aspect_ratio") != "1:1":
        raise RuntimeError("La salida no tiene SAR 1:1")
    if dst.stat().st_size > limit:
        raise RuntimeError(f"La salida sigue superando {a.max_mb:g} MB")
    print(json.dumps({"output": str(dst), "mode": mode, "bytes": dst.stat().st_size,
                      "width": video["width"], "height": video["height"],
                      "sar": video["sample_aspect_ratio"],
                      "duration": info.get("format", {}).get("duration")}, ensure_ascii=False))

if __name__ == "__main__": main()
