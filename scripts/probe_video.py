#!/usr/bin/env python3
"""probe_video.py - Analisis FFprobe del video fuente (regla 6)."""
import json, subprocess


def _frac(v):
    if not v or v in ("0/0", "0", "0:0"):
        return None
    sep = "/" if "/" in v else ":" if ":" in v else None
    if sep:
        a, b = v.split(sep)
        try:
            return float(a) / float(b) if float(b) else None
        except ValueError:
            return None
    try:
        return float(v)
    except ValueError:
        return None


def probe(path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
           "stream=width,height,r_frame_rate,avg_frame_rate,sample_aspect_ratio,"
           "display_aspect_ratio,rotation,codec_name,pix_fmt", "-show_entries",
           "format=duration", "-of", "json", path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffprobe fallo: " + r.stderr[-500:])
    d = json.loads(r.stdout)
    s = d["streams"][0]
    w, h = int(s["width"]), int(s["height"])
    rot = int(float(s.get("rotation") or 0)) % 360
    if rot in (90, 270):
        w, h = h, w
    fps = _frac(s.get("r_frame_rate") or s.get("avg_frame_rate")) or 30.0
    sar = _frac(s.get("sample_aspect_ratio")) or 1.0
    dar_txt = s.get("display_aspect_ratio") or ""
    dar = None
    if ":" in dar_txt:
        try:
            a, b = dar_txt.split(":")
            dar = float(a) / float(b)
        except ValueError:
            dar = None
    if not dar:
        dar = (w / h) * sar
    return {"path": path, "width": int(w), "height": int(h), "rotation": rot,
            "fps": round(fps, 3), "sar": sar, "dar": round(dar, 6),
            "pix_fmt": s.get("pix_fmt", ""), "codec": s.get("codec_name", ""),
            "duration": float(d["format"]["duration"])}


if __name__ == "__main__":
    import sys
    for k, val in probe(sys.argv[1]).items():
        print(f"{k}: {val}")
