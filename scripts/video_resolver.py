#!/usr/bin/env python3
"""video_resolver.py - Capa de descarga con deteccion de plataforma.

Orden (regla del SKILL): yt-dlp / resolvedor existente PRIMERO; el navegador
solamente como fallback (lo ejecuta el agente con browser_*, nunca dentro de
este modulo). Devuelve un VideoJob relleno o marca browser_required.
"""
import os, re, shutil, subprocess, tempfile
from ipaddress import ip_address
from urllib.parse import urlparse

from video_job import VideoJob
import probe_video as pv

YTDLP = shutil.which("yt-dlp") or os.path.expanduser("~/.local/bin/yt-dlp")
DIRECT_EXT = re.compile(r"\.(mp4|mov|webm|m4v|mkv)$", re.I)
YTDLP_PROBE_TIMEOUT = 120
YTDLP_DOWNLOAD_TIMEOUT = 1800
UNSAFE_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
}


class ResolverError(Exception):
    def __init__(self, kind, msg):
        super().__init__(msg)
        self.kind = kind


def _safe_host(host):
    host = (host or "").rstrip(".").casefold()
    if not host or host in UNSAFE_HOSTNAMES:
        return False
    if (host.endswith(".localhost") or host.endswith(".local") or
            host.endswith(".internal") or host.endswith(".lan")):
        return False
    try:
        return ip_address(host).is_global
    except ValueError:
        # DNS names are allowed here. A deployment exposing this bot publicly
        # should additionally enforce egress/DNS policy at the network layer.
        return True


def validate_url(url):
    """Validate an HTTP(S) URL before handing it to yt-dlp."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
    except (TypeError, ValueError) as exc:
        raise ResolverError("invalid_url", "URL invalida") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not host:
        raise ResolverError("invalid_url", "URL invalida")
    if not _safe_host(host):
        raise ResolverError("unsafe_url", "El host de la URL no está permitido")
    return parsed


def detect_platform(url):
    try:
        parsed = urlparse(url)
        host = parsed.hostname
    except (TypeError, ValueError):
        return "invalid"
    if (parsed.scheme.lower() not in {"http", "https"} or not host or
            not _safe_host(host)):
        return "invalid"
    host = host.lower().removeprefix("www.")
    if DIRECT_EXT.search(parsed.path):
        return "direct"
    if host == "tiktok.com" or host.endswith(".tiktok.com"):
        return "tiktok"
    if (host == "x.com" or host.endswith(".x.com") or
            host == "twitter.com" or host.endswith(".twitter.com")):
        return "x"
    if (host == "youtube.com" or host.endswith(".youtube.com") or
            host == "youtu.be"):
        return "youtube"
    if host == "instagram.com" or host.endswith(".instagram.com"):
        return "instagram"
    return "unknown"


def _ytdlp(args):
    if not os.path.exists(YTDLP):
        raise ResolverError("no_ytdlp", f"yt-dlp no encontrado en {YTDLP}")
    timeout = YTDLP_PROBE_TIMEOUT if "--dump-single-json" in args else YTDLP_DOWNLOAD_TIMEOUT
    try:
        r = subprocess.run([YTDLP] + args, capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ResolverError("timeout", f"yt-dlp agotó el timeout de {timeout}s") from exc
    except OSError as exc:
        raise ResolverError("no_ytdlp", f"No se pudo ejecutar yt-dlp: {exc}") from exc
    return r


def _parse_duration(d):
    try:
        return float(d)
    except (TypeError, ValueError):
        return 0.0


def probe_remote(url):
    """Metadata sin descargar. Devuelve (meta_dict, browser_required:bool, razon)."""
    r = _ytdlp(["--no-playlist", "--dump-single-json", "--skip-download", url])
    if r.returncode == 0:
        import json
        try:
            return json.loads(r.stdout), False, ""
        except ValueError:
            pass
    err = r.stderr.lower()
    if any(k in err for k in ("login", "private", "sign in", "authentication")):
        return None, True, "login_required"
    if "private" in err:
        return None, True, "private"
    if "unsupported url" in err:
        return None, False, "unsupported"
    return None, True, "browser_fallback"


def _format_max_filesize(max_bytes):
    if max_bytes is None:
        return None
    try:
        max_bytes = int(max_bytes)
    except (TypeError, ValueError) as exc:
        raise ValueError("El límite de descarga debe ser numérico") from exc
    if max_bytes <= 0:
        raise ValueError("El límite de descarga debe ser positivo")
    megabytes = f"{max_bytes / 1024 / 1024:.6f}".rstrip("0").rstrip(".")
    return f"{megabytes}M"


def download(url, dest_dir=None, max_height=1080, max_bytes=None):
    """Descarga el mejor video <= max_height con audio. Devuelve (ruta, meta)."""
    validate_url(url)
    dest_dir = dest_dir or tempfile.mkdtemp(prefix="vve_job_")
    os.makedirs(dest_dir, exist_ok=True)
    out_tpl = os.path.join(dest_dir, "original.%(ext)s")
    fmt = f"bv*[height<={max_height}]+ba/b[height<={max_height}]"
    args = ["--no-playlist", "-f", fmt]
    max_filesize = _format_max_filesize(max_bytes)
    if max_filesize:
        args += ["--max-filesize", max_filesize]
    args += ["--merge-output-format", "mp4", "-o", out_tpl, url]
    r = _ytdlp(args)
    if r.returncode != 0:
        raise ResolverError("download_failed", "yt-dlp: " + r.stderr[-500:])
    for name in os.listdir(dest_dir):
        if name.startswith("original.") and os.path.getsize(os.path.join(dest_dir, name)) > 0:
            return os.path.join(dest_dir, name), dest_dir
    raise ResolverError("empty_file", "Descarga sin archivo util")


def resolve(url, workdir=None, max_bytes=None):
    """One-shot resolver: devuelve VideoJob (o lanza ResolverError). No usa navegador."""
    validate_url(url)
    plat = detect_platform(url)
    if plat == "invalid":
        raise ResolverError("invalid_url", "URL invalida")
    if plat == "unsupported" or plat == "unknown":
        # dejamos que yt-dlp intente; si falla -> browser_fallback
        pass
    meta, need_browser, reason = probe_remote(url)
    if need_browser:
        job = VideoJob(source_url=url, platform=plat, workdir=workdir or "")
        job.metadata = {"browser_required": True, "reason": reason}
        return job
    if not meta:
        raise ResolverError(reason or "unsupported", "No se pudo resolver la URL")
    job = VideoJob(source_url=url, platform=plat,
                   resolved_url=meta.get("webpage_url", url),
                   title=(meta.get("title") or "").strip(),
                   description=(meta.get("description") or "").strip(),
                   author=meta.get("uploader") or meta.get("channel") or "",
                   duration=_parse_duration(meta.get("duration")),
                   thumbnail=meta.get("thumbnail") or "",
                   date=str(meta.get("upload_date") or ""),
                   metadata=meta)
    job.workdir = workdir or tempfile.mkdtemp(prefix="vve_job_")
    os.makedirs(job.workdir, exist_ok=True)
    path, _ = download(url, dest_dir=job.workdir, max_bytes=max_bytes)
    job.input_file = path
    # Resolución/fps reales del archivo y validación temprana de integridad.
    try:
        actual = pv.probe(path)
    except (OSError, RuntimeError) as exc:
        raise ResolverError("probe_failed", str(exc)) from exc
    job.width, job.height, job.fps = actual["width"], actual["height"], actual["fps"]
    return job
