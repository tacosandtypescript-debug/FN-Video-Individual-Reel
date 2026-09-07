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

def _transcode(src, dst, use_cuda, video_bitrate=None, audio_bitrate="96k"):
    if video_bitrate is None:
        if use_cuda:
            video_codec = ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "23"]
        else:
            video_codec = ["-c:v", "libx264", "-preset", "medium", "-crf", "23"]
    elif use_cuda:
        video_codec = [
            "-c:v", "h264_nvenc", "-preset", "p5", "-b:v", str(video_bitrate),
            "-maxrate", str(video_bitrate), "-bufsize", str(video_bitrate * 2),
        ]
    else:
        video_codec = [
            "-c:v", "libx264", "-preset", "medium", "-b:v", str(video_bitrate),
            "-maxrate", str(video_bitrate), "-bufsize", str(video_bitrate * 2),
        ]
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
         "-vf", "scale=720:1280:force_original_aspect_ratio=decrease:flags=lanczos,"
                "pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1",
         "-map", "0:v:0", "-map", "0:a:0?", *video_codec, "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", str(audio_bitrate), "-shortest",
         "-movflags", "+faststart", str(dst)])


def _bitrate_budget(limit, duration, has_audio):
    """Leave container overhead room so the Telegram limit is real, not best effort."""
    total = max(64_000, int(limit * 8 * 0.88 / max(duration, 0.1)))
    if not has_audio:
        return max(32_000, total), 0
    audio = min(96_000, max(32_000, total // 5))
    return max(32_000, total - audio), audio


def prepare_file(input_path, output_path, max_mb=45):
    """Prepare and validate one Telegram-compatible copy.

    Returns a small JSON-serializable report so a bot can call the same logic
    without spawning this CLI as a child process.
    """
    src = Path(input_path)
    dst = Path(output_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not src.is_file():
        raise FileNotFoundError(f"No existe el video de entrada: {src}")
    if src.resolve() == dst.resolve():
        raise ValueError("La salida debe ser un archivo distinto de la entrada")
    if max_mb <= 0:
        raise ValueError("--max-mb debe ser mayor que cero")
    limit = int(max_mb * 1024 * 1024)
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
        use_cuda = cuda_available()
        try:
            _transcode(src, dst, use_cuda)
        except subprocess.CalledProcessError:
            if not use_cuda:
                raise
            # A visible GPU can still reject an encode because of a driver,
            # session or resource issue.  Keep the advertised CPU fallback
            # functional instead of failing the Telegram delivery.
            use_cuda = False
            _transcode(src, dst, False)
        mode = "reencoded"
        if dst.stat().st_size > limit:
            video_bitrate, audio_bitrate = _bitrate_budget(
                limit, float(source_info.get("format", {}).get("duration") or 0),
                source_audio is not None,
            )
            audio_rate = f"{audio_bitrate}"
            try:
                _transcode(src, dst, use_cuda, video_bitrate, audio_rate)
            except subprocess.CalledProcessError:
                if not use_cuda:
                    raise
                _transcode(src, dst, False, video_bitrate, audio_rate)
            if dst.stat().st_size > limit:
                # A second conservative pass absorbs muxing/encoder overhead
                # and very complex footage near the computed bitrate budget.
                reduced_video = max(24_000, int(video_bitrate * 0.72))
                reduced_audio = max(24_000, int(audio_bitrate * 0.72)) if source_audio else 0
                try:
                    _transcode(src, dst, use_cuda, reduced_video,
                               f"{reduced_audio}")
                except subprocess.CalledProcessError:
                    if not use_cuda:
                        raise
                    _transcode(src, dst, False, reduced_video, f"{reduced_audio}")
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
        raise RuntimeError(f"La salida sigue superando {max_mb:g} MB")
    return {"output": str(dst), "mode": mode, "bytes": dst.stat().st_size,
            "width": video["width"], "height": video["height"],
            "sar": video["sample_aspect_ratio"],
            "duration": info.get("format", {}).get("duration")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--max-mb", type=float, default=45)
    a = ap.parse_args()
    report = prepare_file(a.input, a.output, a.max_mb)
    print(json.dumps(report, ensure_ascii=False))

if __name__ == "__main__": main()
