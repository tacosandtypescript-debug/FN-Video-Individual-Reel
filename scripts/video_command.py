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
import argparse, json, os, re, shutil, sys, tempfile, traceback, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import video_resolver as vr
from video_job import VideoJob
from editorial_proposal import EditorialProposal, EditorialProposalSet
import probe_video as pv
import calculate_layout as cl

FONT = "/home/isaac/.local/share/fonts/Barlow-ExtraBoldItalic.ttf"


def auto_split_title(font, title, cw, fs, max_lines=8, max_width_frac=0.88):
    """Divide el título en líneas seguras; el renderer hace el ajuste final."""
    max_w = int(cw * max_width_frac)
    title = re.sub(r"https?://\S+|www\.\S+", " ", title or "", flags=re.IGNORECASE)
    title = re.sub(r"[#{}|]", " ", title)
    words = re.sub(r"\s+", " ", title.strip().replace("\n", " ")).split()
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
    if len(lines) <= max_lines:
        return lines

    # Do not silently drop the rest of a source title.  Make truncation
    # explicit with an ellipsis while keeping the generated spec parseable.
    lines = lines[:max_lines]
    suffix = "…"
    last = lines[-1]
    while last and cl.line_width(font, f"{last} {suffix}", fs) > max_w:
        last = " ".join(last.split()[:-1])
    lines[-1] = f"{last} {suffix}".strip() if last else suffix
    return lines


def ensure_texts(top_spec, bot_spec, title, cw, fs, author="", font=FONT):
    if not top_spec and author and title.startswith(author + " - "):
        title = title[len(author) + 3:]
    if top_spec:
        top = top_spec
    else:
        lines = auto_split_title(font, title, cw, fs)
        if not lines:
            raise RuntimeError("Sin titulo y sin --top: imposible generar texto")
        top = "\n".join(lines)
    bot = bot_spec or ""
    return top, bot


def run_render(input_file, out, top, bot, preset="tiktok_fortnite", canvas=None,
               gap=None, blur=None, cq=None, diag=False, correct=True):
    import render_video as rv
    return rv.render(input_file, out, top, bot, preset, canvas, gap, blur, cq,
                     None, None, debug=False, diag=diag, correct=correct)


def preset_font(preset_name):
    import render_video as rv
    return rv.resolve_font(rv.Preset(preset_name).get("font", FONT))


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
    os.makedirs(os.path.dirname(os.path.abspath(job_path)), exist_ok=True)
    job.save(job_path)
    print(f"JOB:{job_path}")
    return 0


def cmd_render_approved(job_path, proposal_path, out, preset, canvas, gap, blur, cq, diag):
    """Renderiza exclusivamente una propuesta editorial previamente aprobada."""
    job = VideoJob.load(job_path)
    with open(proposal_path, encoding="utf-8") as fh:
        proposal_data = json.load(fh)
    if "options" in proposal_data:
        proposal_set = EditorialProposalSet.load(proposal_path)
        proposal_set.validate()
        if (os.path.realpath(proposal_set.job_path) !=
                os.path.realpath(job_path)):
            raise ValueError("El set editorial no corresponde a este VideoJob")
        if proposal_set.selected is None:
            raise PermissionError("El set editorial todavía no tiene una opción aprobada")
        proposal = proposal_set.options[proposal_set.selected]
    else:
        proposal = EditorialProposal(**proposal_data)
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


def cmd_run(url, out, top_spec, bot_spec, preset, canvas, gap, blur, cq, diag,
            workdir, cleanup_source=False):
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
        import render_video as rv
        font_size_1080 = rv.Preset(preset).get("font_size_1080", 60)
        fs = cl.scale_1080(font_size_1080, (canvas or (1080, 1920))[1])
        top, bot = ensure_texts(top_spec, bot_spec, job.title, cw, fs, job.author,
                                font=preset_font(preset))
        print("Renderizando...")
        layout, _, _, frame = run_render(job.input_file, out, top, bot, preset,
                                         canvas, gap, blur, cq, diag)
        print("Validando... OK (gaps reales verificados contra el objetivo)")
        print("Edición lista")
        if cleanup_source:
            job.metadata["_vve_source_removed_after_run"] = True
            job.input_file = ""
            job.workdir = ""
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
        top, bot = ensure_texts(
            top_spec, bot_spec,
            os.path.splitext(os.path.basename(path))[0].replace("_", " "),
            cw, fs, font=preset_font(preset))
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
    p = sub.add_parser("resolve", help="descarga y conserva el VideoJob")
    p.add_argument("url")
    p.add_argument("--workdir", default=None)
    p = sub.add_parser("run")
    p.add_argument("url")
    p.add_argument("-o", "--out", required=True)
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
    if a.cmd == "run" and not workdir:
        tmp = tempfile.mkdtemp(prefix="vve_job_")
        workdir = tmp
    elif a.cmd == "resolve" and not workdir:
        workdir = os.path.join(os.getcwd(), ".vve_jobs", uuid.uuid4().hex)
        os.makedirs(workdir, exist_ok=True)
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
                         a.blur, a.cq, a.diag, workdir, cleanup_source=bool(tmp))
        else:
            rc = cmd_local(a.path, a.out, a.top, a.bot, a.preset, canvas, a.gap,
                           a.blur, a.cq, a.diag)
    finally:
        if tmp and os.path.isdir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)   # libera temporales SIEMPRE
    sys.exit(rc)


if __name__ == "__main__":
    main()
