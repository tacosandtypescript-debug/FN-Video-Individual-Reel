#!/usr/bin/env python3
"""render_video.py - Orquestador: preset + geometria + render GPU + validacion.

Uso:
  python3 render_video.py INPUT.mp4 -o SALIDA.mp4 --top top.txt --bot bot.txt
      [--preset tiktok_fortnite] [--canvas 1080x1920] [--gap 32] [--blur 16]
      [--debug-layout] [--diagnostic-frame]
"""
import argparse, json, os, sys, shutil, subprocess

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


def resolve_font(path):
    """Resuelve la fuente del preset sin depender de una ruta personal fija."""
    if path and os.path.isfile(path):
        return path
    if shutil.which("fc-match"):
        try:
            result = subprocess.run(
                ["fc-match", "-f", "%{file}", "Barlow:style=ExtraBold Italic"],
                capture_output=True, text=True, timeout=5,
            )
            matched = result.stdout.strip()
            if result.returncode == 0 and os.path.isfile(matched):
                if path and matched != path:
                    print(f"Fuente no encontrada ({path}); usando {matched}")
                return matched
        except (OSError, subprocess.TimeoutExpired):
            pass
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBoldOblique.ttf",
    ):
        if os.path.isfile(candidate):
            if path:
                print(f"Fuente no encontrada ({path}); usando {candidate}")
            return candidate
    raise FileNotFoundError(
        f"No se encontró una fuente compatible; revisa la fuente del preset: {path}"
    )


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
    font = resolve_font(font or preset["font"])
    outline = preset["outline"]
    wave_hz = preset["wave_hz"]
    fg_radius = cl.scale_1080(preset.get("foreground_corner_radius_1080", 18), ch)
    fg_shadow = preset.get("foreground_shadow", {})
    shadow_enabled = bool(fg_shadow.get("enabled", True))
    shadow_offset = cl.scale_1080(fg_shadow.get("offset_1080", 8), ch)
    shadow_blur = cl.scale_1080(fg_shadow.get("blur_1080", 14), ch)
    shadow_opacity = float(fg_shadow.get("opacity", 0.58))
    safe = preset["safe"]
    encode = dict(preset.get("encode", {}))
    requested_vcodec = str(encode.get("vcodec", "h264_nvenc"))
    use_cuda = requested_vcodec.endswith("_nvenc") and bf.cuda_available()
    if requested_vcodec.endswith("_nvenc") and not use_cuda:
        print("NVENC no disponible; usando el encoder CPU de respaldo")

    probe = pv.probe(video)
    active = dg.active_bounds(video, probe)
    top_lines = cl.parse_text_spec(top_spec, default_size=cl.scale_1080(preset["font_size_1080"], ch))
    bot_lines = cl.parse_text_spec(bot_spec, default_size=cl.scale_1080(preset["font_size_1080"], ch))
    auto_font = preset.get("auto_font", {})
    if auto_font.get("enabled", True):
        safe_text_width = cw - int(cw * safe["left_f"]) - int(cw * safe["right_f"])
        base_fs = cl.scale_1080(preset["font_size_1080"], ch)
        max_fs = cl.scale_1080(auto_font.get("max_size_1080", 84), ch)
        fraction = float(auto_font.get("target_width_fraction", 0.82))
        cl.enlarge_short_lines(top_lines, font, safe_text_width, base_fs, max_fs, fraction)
        cl.enlarge_short_lines(bot_lines, font, safe_text_width, base_fs, max_fs, fraction)
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
    # El objetivo visual se fija antes de cualquier corrección. Las métricas
    # de drawtext pueden diferir del bbox de PIL; por ello no se convierte un
    # primer ajuste correcto en una cascada de desplazamientos.
    target_top_gap, target_bot_gap = layout.gap_top, layout.gap_bot
    for it in range(max_iter):
        cmd, tmpdir, cover = bf.build(video, probe, active, layout, out, blur=blur,
                                      cq=cq, outline=outline, wave=wave, wave_hz=wave_hz,
                                      font=font, fg_radius=fg_radius,
                                      shadow_enabled=shadow_enabled,
                                      shadow_offset=shadow_offset,
                                      shadow_blur=shadow_blur,
                                      shadow_opacity=shadow_opacity,
                                      encode=encode, use_cuda=use_cuda)
        if debug:
            print(f"Background scaled: {cover[0]}x{cover[1]} (cover, AR intacto)")
        rc, err = bf.run(cmd)
        shutil.rmtree(tmpdir, ignore_errors=True)
        if rc != 0:
            raise RuntimeError("ffmpeg: " + err[-1500:])
        vr.validate_output(out, cw, ch)
        frame_png = out + ".chk.png"
        # En clips muy cortos 0.3s puede quedar fuera del stream.
        check_t = min(0.3, max(0.0, probe["duration"] / 2.0))
        vr.extract_frame(out, check_t, frame_png)
        gtop, gbot = vr.measure_gaps(frame_png, layout, *anchors)
        print(f"[check {it}] real arriba={gtop} real abajo={gbot} "
              f"(objetivo {target_top_gap}/{target_bot_gap})")
        top_ok = (gtop is None or (target_top_gap is not None and abs(gtop - target_top_gap) <= 2))
        bot_ok = (gbot is None or (target_bot_gap is not None and abs(gbot - target_bot_gap) <= 2))
        ok = top_ok and bot_ok
        if not correct or ok:
            final_frame = frame_png
            break
        # Superior: si el gap real es demasiado grande, bajar el bloque (dy positivo).
        # Inferior: si el gap real es demasiado grande, subir el bloque (dy negativo).
        d_top = (gtop - target_top_gap) if (gtop is not None and target_top_gap is not None) else 0
        d_bot = (target_bot_gap - gbot) if (gbot is not None and target_bot_gap is not None) else 0
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
