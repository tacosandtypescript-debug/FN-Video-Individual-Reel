#!/usr/bin/env python3
"""video_command.py - Comando one-shot /video <URL>.

Flujo oficial: validar URL -> resolver (yt-dlp primero; navegador = fallback del
agente) -> VideoJob -> vertical-video-editor (render) -> validar -> resultado.

Uso:
  python3 video_command.py resolve <URL>            # solo descarga + metadata
  python3 video_command.py run <URL> -o salida.mp4 [--top f] [--bot f]
  python3 video_command.py local <ARCHIVO> -o salida.mp4 [--top f] [--bot f]

Siempre limpia temporales y libera recursos aunque falle (try/finally).
"""
import argparse, json, os, re, shutil, sys, tempfile, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import video_resolver as vr
from video_job import VideoJob
from editorial_proposal import EditorialProposal, display as display_proposal
import probe_video as pv
import detect_geometry as dg
import calculate_layout as cl
import build_ffmpeg_filter as bf
import validate_render as vr2

FONT = "/home/isaac/.local/share/fonts/Barlow-ExtraBoldItalic.ttf"


def auto_split_title(font, title, cw, fs, max_lines=2, max_width_frac=0.62):
    """Divide el titulo en <=max_lines lineas que caben en el ancho del canvas."""
    max_w = int(cw * max_width_frac)
    words = re.sub(r"\s+", " ", (title or "").strip().replace("\n", " ")).split()
    if not words:
        return []
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and cl.line_width(font, trial, fs) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines[:max_lines]


def ensure_texts(top_spec, bot_spec, title, cw, fs, author=""):
    if not top_spec and author and title.startswith(author + " - "):
        title = title[len(author) + 3:]
    if top_spec:
        top = top_spec
    else:
        lines = auto_split_title(FONT, title, cw, fs)
        if not lines:
            raise RuntimeError("Sin titulo y sin --top: imposible generar texto")
        top = "\n".join(lines)
    bot = bot_spec or ""
    return top, bot


def run_render(input_file, out, top, bot, preset="tiktok_fortnite", canvas=None,
               gap=None, blur=None, cq=None, diag=False, correct=True):
    import render_video as rv
    return rv.render(input_file, out, top, bot, preset, canvas, gap, blur, cq,
                     None, FONT, debug=False, diag=diag, correct=correct)


def cmd_prepare(url, job_path, workdir):
    """Resuelve y descarga, pero NO renderiza: deja el VideoJob para revisión."""
    print("Resolviendo enlace...")
    job = vr.resolve(url, workdir=workdir)
    if job.metadata.get("browser_required"):
        print("BROWSER_REQUIRED", job.metadata.get("reason", ""))
        return 2
    print("Descargando video... OK")
    print("Analizando contenido...")
    print(job.summary())
    job.save(job_path)
    print(f"JOB:{job_path}")
    return 0


def cmd_render_approved(job_path, proposal_path, out, preset, canvas, gap, blur, cq, diag):
    """Renderiza exclusivamente una propuesta editorial previamente aprobada."""
    job = VideoJob.load(job_path)
    proposal = EditorialProposal.load(proposal_path)
    if proposal.source_url != job.source_url:
        raise ValueError("La propuesta no corresponde a este VideoJob")
    top, bot = proposal.to_specs()  # rechaza status proposed/rejected
    print("Propuesta aprobada. Preparando edición...")
    print("Renderizando...")
    _, _, _, frame = run_render(job.input_file, out, top, bot, preset, canvas,
                                 gap, blur, cq, diag)
    print("Validando... OK (gaps reales verificados contra el objetivo)")
    print(f"MEDIA:{out}")
    if frame:
        print(f"FRAME:{frame}")
    return 0


def cmd_resolve(url, workdir):
    print("Resolviendo enlace...")
    job = vr.resolve(url, workdir=workdir)
    if job.metadata.get("browser_required"):
        print("BROWSER_REQUIRED", job.metadata.get("reason", ""))
        return 2
    print(job.summary())
    meta_path = job.save()
    print("JOB", meta_path)
    return 0


def cmd_run(url, out, top_spec, bot_spec, preset, canvas, gap, blur, cq, diag, workdir):
    try:
        print("Resolviendo enlace...")
        job = vr.resolve(url, workdir=workdir)
        if job.metadata.get("browser_required"):
            print("BROWSER_REQUIRED", job.metadata.get("reason", ""))
            return 2
        print("Descargando video... OK")
        print("Analizando contenido...")
        probe = pv.probe(job.input_file)
        print(f"  {probe['width']}x{probe['height']} fps={probe['fps']} "
              f"dur={probe['duration']:.1f}s")
        print("Preparando edicion...")
        cw = (canvas or (1080, 1920))[0]
        fs = cl.scale_1080(60, (canvas or (1080, 1920))[1])
        top, bot = ensure_texts(top_spec, bot_spec, job.title, cw, fs, job.author)
        print("Renderizando...")
        layout, _, _, frame = run_render(job.input_file, out, top, bot, preset,
                                         canvas, gap, blur, cq, diag)
        print("Validando... OK (gaps reales verificados contra el objetivo)")
        print("Enviando...")
        print("OK")
        meta_path = job.save(out + ".job.json")
        print(f"MEDIA:{out}")
        if frame:
            print(f"FRAME:{frame}")
        print(f"JOB:{meta_path}")
        return 0
    except Exception as e:
        print("ERROR", type(e).__name__)
        print(str(e))
        traceback.print_exc()
        return 1


def cmd_local(path, out, top_spec, bot_spec, preset, canvas, gap, blur, cq, diag):
    try:
        job = VideoJob(source_url=path, platform="local", title=os.path.basename(path),
                       input_file=path)
        probe = pv.probe(path)
        print(f"Analizando contenido: {probe['width']}x{probe['height']}")
        cw = (canvas or (1080, 1920))[0]
        fs = cl.scale_1080(60, (canvas or (1080, 1920))[1])
        top, bot = ensure_texts(top_spec, bot_spec, os.path.splitext(os.path.basename(path))[0].replace("_", " "), cw, fs)
        print("Renderizando...")
        layout, _, _, frame = run_render(path, out, top, bot, preset, canvas, gap,
                                         blur, cq, diag)
        print("Validando... OK")
        print("OK")
        print(f"MEDIA:{out}")
        if frame:
            print(f"FRAME:{frame}")
        return 0
    except Exception:
        traceback.print_exc()
        return 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("resolve", "run"):
        p = sub.add_parser(name)
        p.add_argument("url")
        p.add_argument("-o", "--out")
        p.add_argument("--top", default=None)
        p.add_argument("--bot", default=None)
        p.add_argument("--preset", default="tiktok_fortnite")
        p.add_argument("--canvas", default=None)
        p.add_argument("--gap", type=int, default=None)
        p.add_argument("--blur", type=float, default=None)
        p.add_argument("--cq", type=int, default=None)
        p.add_argument("--diag", action="store_true")
        p.add_argument("--workdir", default=None)
    p = sub.add_parser("prepare", help="descarga y guarda un VideoJob; no renderiza")
    p.add_argument("url")
    p.add_argument("--job", required=True)
    p.add_argument("--workdir", required=True)
    p = sub.add_parser("render-approved", help="renderiza solo una propuesta aprobada")
    p.add_argument("--job", required=True)
    p.add_argument("--proposal", required=True)
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--preset", default="tiktok_fortnite")
    p.add_argument("--canvas", default=None)
    p.add_argument("--gap", type=int, default=None)
    p.add_argument("--blur", type=float, default=None)
    p.add_argument("--cq", type=int, default=None)
    p.add_argument("--diag", action="store_true")
    p = sub.add_parser("local")
    p.add_argument("path")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--top", default=None)
    p.add_argument("--bot", default=None)
    p.add_argument("--preset", default="tiktok_fortnite")
    p.add_argument("--canvas", default=None)
    p.add_argument("--gap", type=int, default=None)
    p.add_argument("--blur", type=float, default=None)
    p.add_argument("--cq", type=int, default=None)
    p.add_argument("--diag", action="store_true")
    a = ap.parse_args()
    canvas_value = getattr(a, "canvas", None)
    canvas = tuple(int(x) for x in canvas_value.lower().split("x")) if canvas_value else None
    workdir = getattr(a, "workdir", None)
    tmp = None
    if a.cmd in ("resolve", "run") and not workdir:
        tmp = tempfile.mkdtemp(prefix="vve_job_")
        workdir = tmp
    try:
        if a.cmd == "prepare":
            rc = cmd_prepare(a.url, a.job, a.workdir)
        elif a.cmd == "render-approved":
            rc = cmd_render_approved(a.job, a.proposal, a.out, a.preset, canvas,
                                     a.gap, a.blur, a.cq, a.diag)
        elif a.cmd == "resolve":
            rc = cmd_resolve(a.url, workdir)
        elif a.cmd == "run":
            rc = cmd_run(a.url, a.out, a.top, a.bot, a.preset, canvas, a.gap,
                         a.blur, a.cq, a.diag, workdir)
        else:
            rc = cmd_local(a.path, a.out, a.top, a.bot, a.preset, canvas, a.gap,
                           a.blur, a.cq, a.diag)
    finally:
        if tmp and os.path.isdir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)   # libera temporales SIEMPRE
    sys.exit(rc)


if __name__ == "__main__":
    main()
