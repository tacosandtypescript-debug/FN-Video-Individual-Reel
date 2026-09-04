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

from build_ffmpeg_filter import cuda_available

MAX_BYTES = 45 * 1024 * 1024

def probe(path):
    cmd = ["ffprobe", "-v", "error", "-show_entries",
           "stream=width,height,sample_aspect_ratio,display_aspect_ratio,codec_type,codec_name",
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
    if not src.is_file():
        raise FileNotFoundError(f"No existe el video de entrada: {src}")
    if src.resolve() == dst.resolve():
        raise ValueError("La salida debe ser un archivo distinto de la entrada")
    limit = int(a.max_mb * 1024 * 1024)
    source_info = probe(str(src)); source_streams = source_info.get("streams", [])
    source_video = next((s for s in source_streams if s.get("codec_type") == "video"), None)
    if source_video is None:
        raise RuntimeError("El archivo de entrada no contiene un stream de video")
    source_audio = next((s for s in source_streams if s.get("codec_type") == "audio"), None)
    source_sar_ok = source_video.get("sample_aspect_ratio") == "1:1"
    source_dar_ok = source_video.get("width", 0) * 16 == source_video.get("height", 0) * 9
    source_codec_ok = source_video.get("codec_name") == "h264"
    source_audio_ok = source_audio is None or source_audio.get("codec_name") == "aac"
    if (src.stat().st_size <= limit and source_sar_ok and source_dar_ok
            and source_codec_ok and source_audio_ok):
        shutil.copy2(src, dst)
        mode = "copied"
    else:
        if cuda_available():
            video_codec = ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "23"]
        else:
            video_codec = ["-c:v", "libx264", "-preset", "medium", "-crf", "23"]
        run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
             "-vf", "scale=720:1280:force_original_aspect_ratio=decrease:flags=lanczos,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1",
             "-map", "0:v:0", "-map", "0:a:0?", *video_codec, "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(dst)])
        mode = "reencoded"
    info = probe(str(dst)); streams = info.get("streams", []); video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise RuntimeError("La salida no contiene un stream de video")
    if video.get("width") / video.get("height") != 0.5625:
        raise RuntimeError("La salida no es 9:16")
    if video.get("sample_aspect_ratio") != "1:1":
        raise RuntimeError("La salida no tiene SAR 1:1")
    if video.get("codec_name") != "h264":
        raise RuntimeError("La salida no está codificada en H.264")
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if audio is not None and audio.get("codec_name") != "aac":
        raise RuntimeError("El audio de salida no está codificado en AAC")
    try:
        duration = float(info.get("format", {}).get("duration", 0))
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        raise RuntimeError("La salida no tiene una duración válida")
    if dst.stat().st_size > limit:
        raise RuntimeError(f"La salida sigue superando {a.max_mb:g} MB")
    print(json.dumps({"output": str(dst), "mode": mode, "bytes": dst.stat().st_size,
                      "width": video["width"], "height": video["height"],
                      "sar": video["sample_aspect_ratio"],
                      "duration": info.get("format", {}).get("duration")}, ensure_ascii=False))

if __name__ == "__main__": main()
