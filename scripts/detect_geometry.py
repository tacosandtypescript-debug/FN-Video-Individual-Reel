#!/usr/bin/env python3
"""detect_geometry.py - Imagen activa real via cropdetect (quita barras/letterbox)."""
import re, subprocess

_CROP_RE = re.compile(r"crop=(\d+):(\d+):(\d+):(\d+)")


def active_bounds(path, probe, seconds=3.0):
    if probe["rotation"] in (90, 270):
        return {"x": 0, "y": 0, "w": probe["width"], "h": probe["height"]}
    n = max(1, int(seconds * probe["fps"]))
    cmd = ["ffmpeg", "-v", "info", "-ss", "0", "-i", path,
           "-vf", "cropdetect=limit=24:round=2:reset=0", "-frames:v", str(n),
           "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    crops = _CROP_RE.findall(r.stderr)
    full = {"x": 0, "y": 0, "w": probe["width"], "h": probe["height"]}
    if not crops:
        return full
    cw_, ch_, cx_, cy_ = (int(x) for x in crops[-1])   # cropdetect emite W:H:X:Y
    if cw_ <= 0 or ch_ <= 0 or cw_ > probe["width"] or ch_ > probe["height"]:
        return full
    if cw_ == probe["width"] and ch_ == probe["height"]:
        return full
    return {"x": cx_, "y": cy_, "w": cw_, "h": ch_}


if __name__ == "__main__":
    import sys
    import probe_video as pv
    p = pv.probe(sys.argv[1])
    a = active_bounds(sys.argv[1], p)
    print(f"active_x: {a['x']}\nactive_y: {a['y']}\nactive_width: {a['w']}\nactive_height: {a['h']}")
