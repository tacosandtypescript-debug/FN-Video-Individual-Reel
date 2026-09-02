#!/usr/bin/env python3
"""render_video.py - Orquestador: preset + geometria + render GPU + validacion.

Uso:
  python3 render_video.py INPUT.mp4 -o SALIDA.mp4 --top top.txt --bot bot.txt
      [--preset tiktok_fortnite] [--canvas 1080x1920] [--gap 32] [--blur 16]
      [--debug-layout] [--diagnostic-frame]
"""
import argparse, json, os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import probe_video as pv
import detect_geometry as dg
import calculate_layout as cl
import build_ffmpeg_filter as bf
import validate_render as vr


class Preset:
    def __init__(self, name):
        path = os.path.join(SKILL_DIR, "references", "presets", name + ".json")
        with open(path) as fh:
            self.data = json.load(fh)

    def __getitem__(self, k):
        return self.data[k]

    def get(self, k, d=None):
        return self.data.get(k, d)


def render(video, out, top_spec, bot_spec, preset_name="tiktok_fortnite",
           canvas=None, gap=None, blur=None, cq=None, wave=None, font=None,
           debug=False, diag=False, correct=True, max_iter=3):
    preset = Preset(preset_name)
    cw, ch = canvas or tuple(preset["canvas"])
    gap = gap if gap is not None else cl.scale_1080(preset["gap_1080"], ch)
    spacing = cl.scale_1080(preset["spacing_1080"], ch)
    blur = blur if blur is not None else preset["blur"]
    cq = cq if cq is not None else preset["encode"]["cq"]
    wave = wave if wave is not None else preset["wave"]
    font = font or preset["font"]
    outline = preset["outline"]
    wave_hz = preset["wave_hz"]
    safe = preset["safe"]

    probe = pv.probe(video)
    active = dg.active_bounds(video, probe)
    top_lines = cl.parse_text_spec(top_spec, default_size=cl.scale_1080(preset["font_size_1080"], ch))
    bot_lines = cl.parse_text_spec(bot_spec, default_size=cl.scale_1080(preset["font_size_1080"], ch))
    layout = cl.Layout(cw, ch, active["w"], active["h"], top_lines, bot_lines,
                       gap, spacing, font, wave, safe)

    if debug:
        print("VIDEO ANALYSIS")
        print(f"Source: {probe['width']}x{probe['height']}")
        print(f"Aspect ratio: {probe['dar']:.4f}")
        print(f"Rotation: {probe['rotation']}")
        print("CANVAS")
        print(f"{cw}x{ch}")
        print("FOREGROUND")
        v = layout.video
        print(f"x: {v.x}\ny: {v.y}\nwidth: {v.w}\nheight: {v.h}\nbottom: {v.bottom}")
        print("TEXT")
        print(f"top block height: {layout.top_block.height}")
        print(f"top gap: {layout.gap_top}")
        print(f"bottom block height: {layout.bot_block.height}")
        print(f"bottom gap: {layout.gap_bot}")
        print("BACKGROUND")
        print(f"aspect preserved: true\ncover mode: true\ncrop centered: true\nblur: {blur}")
    else:
        print(layout.debug(f"Source: {probe['width']}x{probe['height']} "
                           f"(active {active['w']}x{active['h']})"))

    anchors = (layout.top_block.lines[-1].color if layout.top_block.lines else None,
               layout.bot_block.lines[0].color if layout.bot_block.lines else None)
    final_frame = None
    for it in range(max_iter):
        cmd, tmpdir, cover = bf.build(video, probe, active, layout, out, blur=blur,
                                      cq=cq, outline=outline, wave=wave, wave_hz=wave_hz,
                                      font=font)
        if debug:
            print(f"Background scaled: {cover[0]}x{cover[1]} (cover, AR intacto)")
        rc, err = bf.run(cmd)
        shutil.rmtree(tmpdir, ignore_errors=True)
        if rc != 0:
            raise RuntimeError("ffmpeg: " + err[-1500:])
        frame_png = out + ".chk.png"
        vr.extract_frame(out, 0.3, frame_png)
        gtop, gbot = vr.measure_gaps(frame_png, layout, *anchors)
        print(f"[check {it}] real arriba={gtop} real abajo={gbot} "
              f"(modelo {layout.gap_top}/{layout.gap_bot})")
        top_ok = (gtop is None or (layout.gap_top is not None and abs(gtop - layout.gap_top) <= 2))
        bot_ok = (gbot is None or (layout.gap_bot is not None and abs(gbot - layout.gap_bot) <= 2))
        ok = top_ok and bot_ok
        if not correct or ok:
            final_frame = frame_png
            break
        d_top = (layout.gap_top - gtop) if (gtop is not None and layout.gap_top is not None) else 0
        d_bot = (layout.gap_bot - gbot) if (gbot is not None and layout.gap_bot is not None) else 0
        if d_top == 0 and d_bot == 0:
            final_frame = frame_png
            break
        layout.top_block.shift(d_top)
        layout.bot_block.shift(d_bot)
        print(f"  correccion: d_top={d_top} d_bot={d_bot}")
        os.remove(frame_png)

    if final_frame and diag:
        diag_out = out + ".diag.png"
        vr.diagnostic_frame(final_frame, layout, diag_out)
        print(f"Diagnostic frame: {diag_out}")
    return layout, probe, active, final_frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--top", required=True)
    ap.add_argument("--bot", required=True)
    ap.add_argument("--preset", default="tiktok_fortnite")
    ap.add_argument("--canvas", default=None)
    ap.add_argument("--gap", type=int, default=None)
    ap.add_argument("--blur", type=float, default=None)
    ap.add_argument("--cq", type=int, default=None)
    ap.add_argument("--wave", type=int, default=None)
    ap.add_argument("--font", default=None)
    ap.add_argument("--debug-layout", action="store_true")
    ap.add_argument("--diagnostic-frame", action="store_true")
    ap.add_argument("--no-correct", action="store_true")
    a = ap.parse_args()
    canvas = tuple(int(x) for x in a.canvas.lower().split("x")) if a.canvas else None
    render(a.video, a.out, a.top, a.bot, a.preset, canvas, a.gap, a.blur, a.cq,
           a.wave, a.font, a.debug_layout, a.diagnostic_frame,
           correct=not a.no_correct)


if __name__ == "__main__":
    main()
