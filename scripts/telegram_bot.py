#!/usr/bin/env python3
"""Telegram adapter for the Fortnite vertical-video editor.

The editor remains independent from Telegram.  This module supplies the
orchestration layer: one isolated job directory per request, three proposal
buttons, owner checks on callbacks, bounded rendering, validated Telegram
transcoding and native ``send_video`` delivery.

Run it with::

    TELEGRAM_BOT_TOKEN=123:abc python3 telegram_bot.py

Applications that already have a Telegram bot can import ``build_application``
or instantiate ``TelegramVideoBot`` and register its handlers themselves.  The
default proposal provider is deliberately conservative and metadata-grounded;
production deployments can inject an editorial/LLM provider implementing
``ProposalProvider``.
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging
import os
import re
import shutil
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import detect_geometry  # noqa: F401  (keeps the scripts import path explicit)
import editorial_proposal as ep
import prepare_telegram
import probe_video
import video_resolver
from editorial_proposal import EditorialProposal, EditorialProposalSet
from video_job import VideoJob


LOGGER = logging.getLogger("fortnite_vertical_video_editor.telegram")
JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")
CALLBACK_RE = r"^vve:[0-9a-f]{32}:[0-2]$"
DEFAULT_MAX_INPUT_MB = 500
DEFAULT_TELEGRAM_DOWNLOAD_MB = 20
DEFAULT_TELEGRAM_MAX_MB = 45
DEFAULT_CAPTION_HASHTAGS = ("#Fortnite",)
GENERIC_PREFIXES = (
    "mira ", "increíble ", "increible ", "brutal ", "no te lo pierdas ",
    "el mejor ", "secreto ", "viral ", "omg ",
)


@dataclass
class BotJob:
    """Persistent state needed to resume/authorize one Telegram job."""

    job_id: str
    chat_id: int
    owner_id: int
    workdir: str
    job_path: str
    proposal_path: str
    master_path: str
    telegram_path: str
    status: str = "created"
    message_id: int = 0
    source_kind: str = "url"
    created_at: float = field(default_factory=time.time)


class ProposalProvider(Protocol):
    """Build an EditorialProposalSet from a resolved VideoJob."""

    def build(self, job: VideoJob) -> EditorialProposalSet:
        ...


def _clean_copy(value: str, limit: int = 240) -> str:
    """Remove markup/URLs that could corrupt a text spec or title display."""
    value = re.sub(r"https?://\S+|www\.\S+", " ", value or "", flags=re.IGNORECASE)
    value = re.sub(r"#([\w-]+)", r"\1", value)
    value = re.sub(r"[{}|]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    for prefix in GENERIC_PREFIXES:
        if value.casefold().startswith(prefix):
            value = value[len(prefix):].lstrip()
            break
    return value[:limit].rstrip()


def _wrap_copy(value: str, max_chars: int = 34, max_lines: int = 2) -> list[str]:
    """Make short, parseable lines for the safe default proposal provider."""
    words = _clean_copy(value).split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        if len(word) > max_chars:
            word = word[: max_chars - 1] + "…"
        trial = f"{current} {word}".strip()
        if current and len(trial) > max_chars:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    if len(lines) <= max_lines:
        return lines
    lines = lines[:max_lines]
    last = lines[-1]
    while len(f"{last} …") > max_chars and last:
        last = " ".join(last.split()[:-1])
    lines[-1] = f"{last} …".strip() if last else "…"
    return lines


def _visible_line(line: str) -> str:
    """Render a proposal line without exposing its internal color markup."""
    text = ep._split_top_level(line)[0]
    return re.sub(r"\{([^{}|]+)\|#?[0-9A-Fa-f]{6}\}", r"\1", text)


def _display_text(value: str, limit: int) -> str:
    """Keep ORIGINAL metadata readable without changing its published text."""
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value or "")
    return value[:limit].rstrip()


def _editorial_style(preset_name: str) -> tuple[tuple[str, ...], int]:
    """Read the word-accent palette from the active visual preset."""
    fallback = ep.DEFAULT_ACCENT_PALETTE, ep.MAX_ACCENT_COLORS
    path = ROOT / "references" / "presets" / f"{preset_name}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        style = data.get("editorial_colors", {})
        palette = tuple(style.get("palette", ep.DEFAULT_ACCENT_PALETTE))
        maximum = int(style.get("max_highlights", ep.MAX_ACCENT_COLORS))
        if (not palette or maximum <= 0 or
                any(not isinstance(color, str) or len(color.lstrip("#")) != 6
                    or any(char not in ep.HEX for char in color.lstrip("#").upper())
                    for color in palette)):
            return fallback
        return palette, min(maximum, ep.MAX_ACCENT_COLORS, len(palette))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return fallback


class MetadataProposalProvider:
    """Safe fallback when no editorial/LLM provider is injected.

    It only uses the source title, description and resolver metadata.  It is
    intentionally factual rather than pretending to infer a Fortnite mechanic
    that the bot has not actually analyzed.
    """

    def __init__(self, palette=None, max_highlights=None):
        self.palette = tuple(palette or ep.DEFAULT_ACCENT_PALETTE)
        self.max_highlights = (
            ep.MAX_ACCENT_COLORS if max_highlights is None
            else max(0, int(max_highlights))
        )

    def build(self, job: VideoJob) -> EditorialProposalSet:
        title = _wrap_copy(job.title) or ["VIDEO DE FORTNITE"]
        description = _wrap_copy((job.description or "").split("\n", 1)[0])
        author = _clean_copy(job.author, 24)
        platform = _clean_copy(job.platform.upper() or "ORIGEN", 20)
        date = _clean_copy(job.date, 18)

        bottom_1 = description or ["CONTENIDO DEL VIDEO"]
        bottom_2 = _wrap_copy(f"PUBLICADO POR {author}") if author else [f"ORIGEN: {platform}"]
        context = f"PUBLICADO EN {platform}"
        if date:
            context += f" · {date}"
        bottom_3 = _wrap_copy(context) or ["CONTEXTO DEL VIDEO"]
        bottoms = [bottom_1, bottom_2, bottom_3]
        seen: set[str] = set()
        for index, bottom in enumerate(bottoms):
            key = " ".join(bottom).casefold()
            if key in seen:
                bottoms[index] = [f"CONTEXTO {index + 1}"]
            seen.add(" ".join(bottoms[index]).casefold())
        bottom_1, bottom_2, bottom_3 = bottoms

        options = [
            EditorialProposal(
                source_url=job.source_url,
                original_title=job.title,
                original_description=job.description,
                author=job.author,
                analysis="Resultado: usa únicamente la descripción disponible y confirmada por la fuente.",
                top=title,
                bottom=bottom_1,
                color_notes="Se aplicarán acentos automáticos solo a palabras informativas.",
            ),
            EditorialProposal(
                source_url=job.source_url,
                original_title=job.title,
                original_description=job.description,
                author=job.author,
                analysis="Fuente: usa el autor confirmado y no infiere una mecánica no verificada.",
                top=title,
                bottom=bottom_2,
                color_notes="Se aplicarán acentos automáticos solo a palabras informativas.",
            ),
            EditorialProposal(
                source_url=job.source_url,
                original_title=job.title,
                original_description=job.description,
                author=job.author,
                analysis="Contexto: opción basada en plataforma y fecha cuando están disponibles.",
                top=title,
                bottom=bottom_3,
                color_notes="Se aplicarán acentos automáticos solo a palabras informativas.",
            ),
        ]
        proposal_set = EditorialProposalSet(job_path=job.workdir + "/video_job.json", options=options)
        ep.apply_semantic_colors(
            proposal_set,
            palette=self.palette,
            max_highlights=self.max_highlights,
        )
        proposal_set.validate()
        return proposal_set


class JobStore:
    """Small filesystem-backed store; callback data only contains a job UUID."""

    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _validate_id(self, job_id: str) -> None:
        if not JOB_ID_RE.fullmatch(job_id):
            raise ValueError("job_id inválido")

    def _dir(self, job_id: str) -> Path:
        self._validate_id(job_id)
        return self.root / job_id

    def create(self, chat_id: int, owner_id: int, source_kind: str) -> BotJob:
        job_id = uuid.uuid4().hex
        workdir = self._dir(job_id)
        workdir.mkdir(parents=True, exist_ok=False)
        job = BotJob(
            job_id=job_id,
            chat_id=int(chat_id),
            owner_id=int(owner_id),
            workdir=str(workdir),
            job_path=str(workdir / "video_job.json"),
            proposal_path=str(workdir / "proposal_set.json"),
            master_path=str(workdir / "master.mp4"),
            telegram_path=str(workdir / "telegram.mp4"),
            source_kind=source_kind,
        )
        self.save(job)
        return job

    def save(self, job: BotJob) -> None:
        expected = self._dir(job.job_id)
        if Path(job.workdir).expanduser().resolve() != expected:
            raise ValueError("El trabajo apunta fuera del almacén configurado")
        expected.mkdir(parents=True, exist_ok=True)
        target = expected / "manifest.json"
        temporary = expected / ".manifest.json.tmp"
        temporary.write_text(json.dumps(asdict(job), ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
        os.replace(temporary, target)

    def load(self, job_id: str) -> BotJob | None:
        path = self._dir(job_id) / "manifest.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        job = BotJob(**data)
        expected = self._dir(job_id)
        if Path(job.workdir).expanduser().resolve() != expected:
            raise ValueError("Manifest de trabajo inválido")
        return job

    def cleanup(self, job: BotJob) -> None:
        """Remove exactly one completed job directory, never the store root."""
        expected = self._dir(job.job_id)
        if expected == self.root or expected.parent != self.root:
            raise ValueError("Refusing to clean an unsafe job path")
        if expected.exists():
            shutil.rmtree(expected)


class BrowserRequired(RuntimeError):
    pass


class TelegramPipeline:
    """Blocking editor operations exposed through ``asyncio.to_thread``."""

    def __init__(self, store: JobStore, preset: str = "tiktok_fortnite",
                 max_input_mb: float = DEFAULT_MAX_INPUT_MB,
                 telegram_max_mb: float = DEFAULT_TELEGRAM_MAX_MB):
        self.store = store
        self.preset = preset
        if max_input_mb <= 0 or telegram_max_mb <= 0:
            raise ValueError("Los límites de tamaño deben ser mayores que cero")
        self.max_input_bytes = int(max_input_mb * 1024 * 1024)
        self.telegram_max_mb = telegram_max_mb

    def prepare_url(self, record: BotJob, url: str) -> VideoJob:
        job = video_resolver.resolve(
            url, workdir=record.workdir, max_bytes=self.max_input_bytes
        )
        if job.metadata.get("browser_required"):
            raise BrowserRequired(job.metadata.get("reason", "browser_fallback"))
        self._check_input(record, job.input_file)
        job.job_id = record.job_id
        job.save(record.job_path)
        return job

    def prepare_file(self, record: BotJob, path: str, original_name: str = "video.mp4") -> VideoJob:
        source = Path(path)
        target = Path(record.workdir) / "original.mp4"
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        self._check_input(record, str(target))
        metadata = probe_video.probe(str(target))
        job = VideoJob(
            job_id=record.job_id,
            source_url=f"telegram://{record.job_id}",
            resolved_url=f"telegram://{record.job_id}",
            platform="telegram",
            title=_clean_copy(Path(original_name).stem) or "VIDEO DE FORTNITE",
            duration=metadata["duration"],
            width=metadata["width"],
            height=metadata["height"],
            fps=metadata["fps"],
            input_file=str(target),
            workdir=record.workdir,
            metadata={"source": "telegram", "original_name": original_name},
        )
        job.save(record.job_path)
        return job

    def _check_input(self, record: BotJob, path: str) -> None:
        if not path or not Path(path).is_file():
            raise RuntimeError("No se obtuvo un archivo de video válido")
        if Path(path).stat().st_size > self.max_input_bytes:
            raise RuntimeError(
                f"El video supera el límite de entrada de {self.max_input_bytes / 1024 / 1024:g} MB"
            )

    def render(self, record: BotJob) -> tuple[dict[str, Any], str | None]:
        import render_video

        job = VideoJob.load(record.job_path)
        proposal_set = EditorialProposalSet.load(record.proposal_path)
        proposal_set.validate()
        if (Path(proposal_set.job_path).expanduser().resolve() !=
                Path(record.job_path).expanduser().resolve()):
            raise RuntimeError("La propuesta no pertenece a este trabajo")
        if proposal_set.selected is None:
            raise RuntimeError("El trabajo todavía no tiene una propuesta aprobada")
        proposal = proposal_set.options[proposal_set.selected]
        if proposal.source_url != job.source_url:
            raise RuntimeError("La propuesta aprobada no corresponde al video")
        top, bottom = proposal.to_specs()
        Path(record.master_path).parent.mkdir(parents=True, exist_ok=True)
        _, _, _, frame = render_video.render(
            job.input_file,
            record.master_path,
            top,
            bottom,
            preset_name=self.preset,
            correct=True,
            diag=False,
        )
        if not Path(record.master_path).is_file():
            raise RuntimeError("El render no produjo el archivo maestro")
        report = prepare_telegram.prepare_file(
            record.master_path,
            record.telegram_path,
            max_mb=self.telegram_max_mb,
        )
        thumbnail = None
        if frame:
            thumbnail = prepare_telegram.prepare_thumbnail(
                frame, str(Path(record.workdir) / "thumbnail.jpg")
            )
        return report, thumbnail


def _format_proposals(job: VideoJob, proposal_set: EditorialProposalSet) -> str:
    """Format the review message under Telegram's 4096-character limit."""
    proposal_set.validate()
    lines = [
        "ORIGINAL",
        _display_text(job.title, 400) or "(sin título)",
        _display_text(job.description, 700),
        "",
        "ANÁLISIS",
    ]
    for index, proposal in enumerate(proposal_set.options, 1):
        lines.extend([
            "",
            f"OPCIÓN {index}",
            "ARRIBA:",
            "\n".join(f"• {_visible_line(line)}" for line in proposal.top),
            "ABAJO:",
            "\n".join(f"• {_visible_line(line)}" for line in proposal.bottom),
            proposal.analysis or "(sin análisis)",
            f"COLOR: {proposal.color_notes or 'revisión manual'}",
        ])
    lines.extend(["", "Pulsa una opción para aprobarla y renderizarla."])
    text = "\n".join(lines).strip()
    return text[:4000] + ("…" if len(text) > 4000 else "")


def _caption(proposal: EditorialProposal) -> str:
    text = " ".join(_visible_line(line) for line in proposal.top + proposal.bottom)
    hashtags = " ".join(DEFAULT_CAPTION_HASHTAGS)
    if not hashtags:
        return text[:1024]
    available = max(0, 1024 - len(hashtags) - 1)
    prefix = text[:available].rstrip()
    return "\n".join(part for part in (prefix, hashtags) if part)


class TelegramVideoBot:
    """Handlers and orchestration state for python-telegram-bot 22.x."""

    def __init__(self, store: JobStore, pipeline: TelegramPipeline | None = None,
                 proposal_provider: ProposalProvider | None = None,
                 max_render_concurrency: int = 1,
                 keep_files: bool = False,
                 max_active_jobs: int = 3,
                 allowed_user_ids: set[int] | None = None):
        self.store = store
        self.pipeline = pipeline or TelegramPipeline(store)
        (self.editorial_palette,
         self.max_editorial_highlights) = _editorial_style(self.pipeline.preset)
        self.proposal_provider = proposal_provider or MetadataProposalProvider(
            self.editorial_palette,
            self.max_editorial_highlights,
        )
        self.render_slots = asyncio.Semaphore(max(1, int(max_render_concurrency)))
        self.keep_files = keep_files
        if max_active_jobs <= 0:
            raise ValueError("max_active_jobs debe ser mayor que cero")
        self.max_active_jobs = int(max_active_jobs)
        self.allowed_user_ids = {int(user_id) for user_id in (allowed_user_ids or set())}
        self._tasks: set[asyncio.Task[Any]] = set()
        self._job_locks: dict[str, asyncio.Lock] = {}
        self._active_jobs: set[str] = set()

    def _spawn(self, coroutine: Any, job_id: str | None = None) -> None:
        if job_id:
            self._active_jobs.add(job_id)

        async def tracked() -> None:
            try:
                await coroutine
            finally:
                if job_id:
                    self._active_jobs.discard(job_id)

        task = asyncio.create_task(tracked())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _lock_for(self, job_id: str) -> asyncio.Lock:
        return self._job_locks.setdefault(job_id, asyncio.Lock())

    def _authorized(self, user: Any) -> bool:
        return not self.allowed_user_ids or (
            user is not None and int(user.id) in self.allowed_user_ids
        )

    def _capacity_available(self) -> bool:
        return len(self._active_jobs) < self.max_active_jobs

    async def _edit_status(self, bot: Any, job: BotJob, text: str,
                           reply_markup: Any = None) -> None:
        try:
            await bot.edit_message_text(
                chat_id=job.chat_id,
                message_id=job.message_id,
                text=text,
                reply_markup=reply_markup,
            )
        except Exception:
            LOGGER.debug("No se pudo editar el mensaje de estado", exc_info=True)

    async def start(self, update: Any, context: Any) -> None:
        await update.effective_message.reply_text(
            "Envía /video <URL> o escribe /video y después adjunta un MP4.\n"
            "Revisaré tres propuestas antes de renderizar."
        )

    async def video_command(self, update: Any, context: Any) -> None:
        message = update.effective_message
        if not message:
            return
        if not self._authorized(update.effective_user):
            await message.reply_text("Este bot no está habilitado para este usuario.")
            return
        args = list(getattr(context, "args", []) or [])
        if not args:
            context.chat_data["awaiting_media"] = True
            await message.reply_text("Ahora adjunta el video como video o documento MP4.")
            return
        context.chat_data.pop("awaiting_media", None)
        if len(args) != 1:
            await message.reply_text("Uso: /video https://enlace-del-video")
            return
        url = args[0].strip()
        if video_resolver.detect_platform(url) == "invalid":
            await message.reply_text("La URL no parece válida. Usa http:// o https://.")
            return
        await self._start_url(update, context.bot, url)

    async def _start_url(self, update: Any, bot: Any, url: str) -> None:
        message = update.effective_message
        user = update.effective_user
        if not message or not user:
            return
        if not self._capacity_available():
            await message.reply_text("Hay tres trabajos en curso; espera a que termine uno.")
            return
        record = self.store.create(message.chat_id, user.id, "url")
        status = await message.reply_text(f"Trabajo {record.job_id[:8]}: resolviendo y descargando…")
        record.message_id = status.message_id
        record.status = "preparing"
        self.store.save(record)
        self._spawn(self._prepare_url_task(bot, record, url), record.job_id)

    async def _prepare_url_task(self, bot: Any, record: BotJob, url: str) -> None:
        try:
            job = await asyncio.to_thread(self.pipeline.prepare_url, record, url)
            current = self.store.load(record.job_id)
            if current is None or current.status == "cancelled":
                return
            await self._offer_proposals(bot, record, job)
        except BrowserRequired as exc:
            await self._fail(bot, record, "Este enlace requiere sesión o un navegador conectado: " + str(exc))
        except Exception as exc:
            LOGGER.exception("Preparación URL fallida para %s", record.job_id)
            await self._fail(bot, record, f"No pude preparar el video ({type(exc).__name__}). Trabajo: {record.job_id[:8]}")

    async def _call_provider(self, job: VideoJob) -> EditorialProposalSet:
        build = self.proposal_provider.build
        if inspect.iscoroutinefunction(build):
            result = await build(job)
        else:
            result = await asyncio.to_thread(build, job)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, EditorialProposalSet):
            raise TypeError("El proposal provider debe devolver EditorialProposalSet")
        # Enforce the same editorial style for the metadata fallback and for an
        # injected LLM/provider: white is the base, only informative words get
        # accents, and stopwords are rejected by proposal validation.
        ep.apply_semantic_colors(
            result,
            palette=self.editorial_palette,
            max_highlights=self.max_editorial_highlights,
        )
        result.validate()
        return result

    async def _offer_proposals(self, bot: Any, record: BotJob, job: VideoJob) -> None:
        current = self.store.load(record.job_id)
        if current is None or current.status == "cancelled":
            return
        record.status = "preparing_proposals"
        self.store.save(record)
        proposal_set = await self._call_provider(job)
        current = self.store.load(record.job_id)
        if current is None or current.status == "cancelled":
            return
        proposal_set.job_path = record.job_path
        proposal_set.validate()
        if any(option.source_url != job.source_url for option in proposal_set.options):
            raise ValueError("Las propuestas no corresponden al origen resuelto")
        proposal_set.save(record.proposal_path)
        record.status = "awaiting_approval"
        self.store.save(record)
        keyboard = self._proposal_keyboard(record.job_id)
        await self._edit_status(bot, record, _format_proposals(job, proposal_set), keyboard)

    @staticmethod
    def _proposal_keyboard(job_id: str) -> Any:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"OPCIÓN {i}", callback_data=f"vve:{job_id}:{i - 1}")]
            for i in range(1, 4)
        ])

    async def media(self, update: Any, context: Any) -> None:
        message = update.effective_message
        user = update.effective_user
        if not message or not user:
            return
        if not self._authorized(user):
            return
        caption = (message.caption or "").strip().casefold()
        waiting = bool(context.chat_data.pop("awaiting_media", False))
        if (not waiting and
                not re.match(r"^/video(?:@[^\s]+)?(?:\s|$)", caption)):
            return
        media = message.video
        original_name = "video.mp4"
        if media is None and message.document:
            mime = (message.document.mime_type or "").casefold()
            name = message.document.file_name or "video.mp4"
            if not mime.startswith("video/") and Path(name).suffix.casefold() not in {".mp4", ".mov", ".webm", ".mkv"}:
                await message.reply_text("El documento debe ser un video MP4/MOV/WebM/MKV.")
                return
            media = message.document
            original_name = name
        if media is None:
            await message.reply_text("No encontré un video adjunto.")
            return
        if not self._capacity_available():
            await message.reply_text("Hay tres trabajos en curso; espera a que termine uno.")
            return
        size = getattr(media, "file_size", None)
        telegram_limit = DEFAULT_TELEGRAM_DOWNLOAD_MB * 1024 * 1024
        if size and size > min(self.pipeline.max_input_bytes, telegram_limit):
            await message.reply_text("El archivo supera el límite configurado para entrada.")
            return
        record = self.store.create(message.chat_id, user.id, "telegram")
        status = await message.reply_text(f"Trabajo {record.job_id[:8]}: descargando el archivo…")
        record.message_id = status.message_id
        record.status = "preparing"
        self.store.save(record)
        self._spawn(self._prepare_media_task(context.bot, record, media, original_name), record.job_id)

    async def _prepare_media_task(self, bot: Any, record: BotJob, media: Any,
                                  original_name: str) -> None:
        try:
            telegram_file = await bot.get_file(media.file_id)
            target = Path(record.workdir) / "original.mp4"
            await telegram_file.download_to_drive(custom_path=target)
            job = await asyncio.to_thread(
                self.pipeline.prepare_file, record, str(target), original_name
            )
            current = self.store.load(record.job_id)
            if current is None or current.status == "cancelled":
                return
            await self._offer_proposals(bot, record, job)
        except Exception as exc:
            LOGGER.exception("Preparación de adjunto fallida para %s", record.job_id)
            await self._fail(bot, record, f"No pude preparar el archivo ({type(exc).__name__}). Trabajo: {record.job_id[:8]}")

    async def approval_callback(self, update: Any, context: Any) -> None:
        query = update.callback_query
        if not query or not query.data:
            return
        match = re.fullmatch(r"vve:([0-9a-f]{32}):([0-2])", query.data)
        if not match:
            await query.answer("Botón inválido", show_alert=True)
            return
        job_id, index_text = match.groups()
        try:
            record = self.store.load(job_id)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            LOGGER.exception("Manifest inválido para %s", job_id)
            await query.answer("Este trabajo ya no está disponible.", show_alert=True)
            return
        user = update.effective_user
        if (record is None or not user or record.chat_id != update.effective_chat.id
                or record.owner_id != user.id or not self._authorized(user)):
            await query.answer("Este trabajo no pertenece a esta conversación.", show_alert=True)
            return
        async with self._lock_for(job_id):
            record = self.store.load(job_id)
            if record is None or record.status != "awaiting_approval":
                await query.answer("Este trabajo ya fue procesado.", show_alert=True)
                return
            proposal_set = EditorialProposalSet.load(record.proposal_path)
            picked = proposal_set.choose(int(index_text))
            proposal_set.save(record.proposal_path)
            record.status = "rendering"
            self.store.save(record)
        await query.answer()
        await self._edit_status(context.bot, record,
                                f"Opción aprobada para {job_id[:8]}. Renderizando y validando…")
        self._spawn(self._render_and_send(context.bot, record, picked), record.job_id)

    async def _render_and_send(self, bot: Any, record: BotJob,
                               approved: EditorialProposal) -> None:
        try:
            async with self.render_slots:
                report, frame = await asyncio.to_thread(self.pipeline.render, record)
            current = self.store.load(record.job_id)
            if current is None or current.status == "cancelled":
                return
            record.status = "sending"
            self.store.save(record)
            await self._send_video(bot, record, approved, frame)
            record.status = "sent"
            if self.keep_files:
                self.store.save(record)
            else:
                self.store.cleanup(record)
            await self._edit_status(
                bot, record,
                f"✅ Video enviado ({report['width']}×{report['height']}, {report['bytes']} bytes).",
            )
        except Exception as exc:
            LOGGER.exception("Render/entrega fallida para %s", record.job_id)
            await self._fail(bot, record, f"No pude completar el render ({type(exc).__name__}). Trabajo: {record.job_id[:8]} queda guardado para revisar.")

    async def _send_video(self, bot: Any, record: BotJob,
                          proposal: EditorialProposal, frame: str | None) -> None:
        video_path = Path(record.telegram_path)
        thumb_path = (Path(frame) if frame
                      else Path(record.workdir) / "thumbnail.jpg")
        with video_path.open("rb") as video:
            if thumb_path.is_file():
                with thumb_path.open("rb") as thumbnail:
                    await bot.send_video(
                        chat_id=record.chat_id,
                        video=video,
                        thumbnail=thumbnail,
                        caption=_caption(proposal),
                        supports_streaming=True,
                    )
            else:
                await bot.send_video(
                    chat_id=record.chat_id,
                    video=video,
                    caption=_caption(proposal),
                    supports_streaming=True,
                )

    async def cancel(self, update: Any, context: Any) -> None:
        message = update.effective_message
        user = update.effective_user
        args = list(getattr(context, "args", []) or [])
        if not message:
            return
        if not user or len(args) != 1:
            await message.reply_text("Uso: /cancel <job_id>")
            return
        record = self.store.load(args[0])
        if record is None or record.chat_id != message.chat_id or record.owner_id != user.id:
            await message.reply_text("No encontré ese trabajo en esta conversación.")
            return
        if record.status in {"sent", "failed", "cancelled"}:
            await message.reply_text(f"El trabajo ya está en estado {record.status}.")
            return
        record.status = "cancelled"
        self.store.save(record)
        await message.reply_text(f"Trabajo {record.job_id[:8]} cancelado. Los archivos se conservan temporalmente.")

    async def cleanup(self, update: Any, context: Any) -> None:
        message = update.effective_message
        user = update.effective_user
        args = list(getattr(context, "args", []) or [])
        if not message:
            return
        if not user or len(args) != 1:
            await message.reply_text("Uso: /cleanup <job_id>")
            return
        try:
            record = self.store.load(args[0])
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            record = None
        if record is None or record.chat_id != message.chat_id or record.owner_id != user.id:
            await message.reply_text("No encontré ese trabajo en esta conversación.")
            return
        if (record.status in {"preparing", "preparing_proposals", "rendering", "sending"}
                or record.job_id in self._active_jobs):
            await message.reply_text("Espera a que termine o usa /cancel antes de limpiar el trabajo.")
            return
        self.store.cleanup(record)
        await message.reply_text(f"Trabajo {record.job_id[:8]} y sus archivos eliminados.")

    async def _fail(self, bot: Any, record: BotJob, text: str) -> None:
        record.status = "failed"
        try:
            self.store.save(record)
        except Exception:
            LOGGER.exception("No se pudo guardar el estado fallido")
        await self._edit_status(bot, record, "❌ " + text)

    async def error(self, update: Any, context: Any) -> None:
        LOGGER.error("Unhandled Telegram error", exc_info=context.error)


def build_application(token: str | None = None, *, jobs_dir: str | None = None,
                      preset: str = "tiktok_fortnite",
                      max_render_concurrency: int = 1,
                      max_active_jobs: int = 3,
                      max_input_mb: float = DEFAULT_MAX_INPUT_MB,
                      telegram_max_mb: float = DEFAULT_TELEGRAM_MAX_MB,
                      proposal_provider: ProposalProvider | None = None,
                      keep_files: bool = False) -> Any:
    """Create a python-telegram-bot Application ready for polling/webhook use."""
    try:
        from telegram import Update
        from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters
    except ImportError as exc:
        raise RuntimeError(
            "Instala python-telegram-bot con requirements.txt para usar la integración Telegram"
        ) from exc
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Falta TELEGRAM_BOT_TOKEN")
    root = jobs_dir or os.environ.get("VVE_JOBS_DIR", str(ROOT / ".vve_jobs"))
    store = JobStore(root)
    pipeline = TelegramPipeline(store, preset=preset, max_input_mb=max_input_mb,
                                telegram_max_mb=telegram_max_mb)
    raw_allowed = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "")
    try:
        allowed_user_ids = {int(value.strip()) for value in raw_allowed.split(",") if value.strip()}
    except ValueError as exc:
        raise RuntimeError("TELEGRAM_ALLOWED_USER_IDS debe ser una lista de enteros") from exc
    service = TelegramVideoBot(
        store,
        pipeline=pipeline,
        proposal_provider=proposal_provider,
        max_render_concurrency=max_render_concurrency,
        max_active_jobs=max_active_jobs,
        allowed_user_ids=allowed_user_ids,
        keep_files=keep_files,
    )
    application = Application.builder().token(token).concurrent_updates(8).build()
    application.bot_data["video_service"] = service
    application.add_handler(CommandHandler("start", service.start))
    application.add_handler(CommandHandler("video", service.video_command))
    application.add_handler(CommandHandler("cancel", service.cancel))
    application.add_handler(CommandHandler("cleanup", service.cleanup))
    application.add_handler(CallbackQueryHandler(service.approval_callback, pattern=CALLBACK_RE))
    application.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, service.media))
    application.add_error_handler(service.error)
    # Explicitly return all update types so callback buttons and media updates
    # are not filtered out when this application is started with polling.
    application.bot_data["allowed_updates"] = Update.ALL_TYPES
    return application


def main() -> None:
    parser = argparse.ArgumentParser(description="Bot Telegram del editor vertical de Fortnite")
    parser.add_argument("--token", default=None)
    parser.add_argument("--jobs-dir", default=None)
    parser.add_argument("--preset", default="tiktok_fortnite")
    parser.add_argument("--max-renders", type=int, default=1)
    parser.add_argument("--max-jobs", type=int, default=3)
    parser.add_argument("--max-input-mb", type=float, default=DEFAULT_MAX_INPUT_MB)
    parser.add_argument("--telegram-max-mb", type=float, default=DEFAULT_TELEGRAM_MAX_MB)
    parser.add_argument("--keep-files", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    application = build_application(
        args.token,
        jobs_dir=args.jobs_dir,
        preset=args.preset,
        max_render_concurrency=args.max_renders,
        max_active_jobs=args.max_jobs,
        max_input_mb=args.max_input_mb,
        telegram_max_mb=args.telegram_max_mb,
        keep_files=args.keep_files,
    )
    from telegram import Update
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
