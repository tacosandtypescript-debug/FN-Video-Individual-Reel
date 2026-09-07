#!/usr/bin/env python3
"""editorial_proposal.py - Contrato editorial entre /video y el render.

No traduce ni inventa contexto: el agente analiza titulo/descripcion y crea una
propuesta en español. Este modulo persiste la propuesta, valida colores y evita
que FFmpeg reciba texto sin aprobación explícita.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, asdict, field
from pathlib import Path

HEX = "0123456789ABCDEF"
SEGMENT = re.compile(r"\{[^{}|]+\|#?[0-9A-Fa-f]{6}\}")
WORD = re.compile(r"[\wÀ-ÿ][\wÀ-ÿ'’\-]*", re.UNICODE)
MAX_ACCENT_COLORS = 4
MAX_LOGICAL_LINES_PER_BLOCK = 8
DEFAULT_ACCENT_PALETTE = ("B84DFF", "42E8FF", "FFDD00", "FF39D7")
# Function words are deliberately excluded from automatic highlighting. This
# covers Spanish copy and English metadata that often arrives from X/TikTok.
EDITORIAL_STOPWORDS = frozenset("a al algo alguna algunas alguno algunos ante antes aquel aquella aquellas aquellos aqui asi bajo cada como con contra cual cuales cuando de del desde donde dos e el ella ellas ello ellos en entre era es esa esas ese eso esos esta estas este esto estos fue han hasta hay la las le les lo los mas me mi mis mucha muchas mucho muchos muy ni no nos o para pero por porque que quien se sin sobre son su sus tambien te tu tus un una unas uno unos y ya yo about after again all am an and any are as at be because been before being but by can could did do does doing down for from had has have he her here hers herself him himself his how i if in into is it its itself just me more most my myself nor not of on or our ours ourselves out over own same she should so some such than that the their theirs them themselves then there these they this those through to too under until up was we were what when where which while who whom why will with would you your yours".split())
EDITORIAL_WEAK_WORDS = frozenset("video videos contenido publicado origen contexto".split())
IMPORTANT_SHORT_WORDS = frozenset("xp fncs uefn pvp pve vbucks v-bucks x ii iii".split())
IMPORTANT_TERMS = frozenset("fortnite temporada temporadas season seasons capitulo chapter evento eventos actualizacion update novedad novedades mapa mapas modo modos skin skins traje trajes arma armas rifle escopeta espada victoria victorias victory eliminacion eliminaciones kill kills glitch bug bugs hack truco trucos recompensa recompensas nivel niveles xp experiencia boss bosses jefe final coche coches vehiculo vehiculos isla islas torneo torneos ranked competitivo competitiva regreso regresa nuevo nueva nuevos nuevas llega llegan cambio cambios añadido anade añade disponible gratis".split())
GENERIC_HOOKS = (
    "mira",
    "increíble",
    "increible",
    "brutal",
    "no te lo pierdas",
    "el mejor",
    "secreto",
    "viral",
    "omg",
)


def _split_top_level(value):
    out, cur, depth = [], [], 0
    for ch in value:
        if ch == "{": depth += 1
        elif ch == "}" and depth: depth -= 1
        if ch == "|" and depth == 0:
            out.append("".join(cur)); cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def _line(line):
    """Normaliza una linea TEXTO|RRGGBB|SIZE opcional."""
    parts = [x.strip() for x in _split_top_level(line)]
    if not parts or not parts[0]:
        raise ValueError("Una línea editorial no puede estar vacía")
    color = (parts[1] if len(parts) > 1 and parts[1] else "FFFFFF").lstrip("#").upper()
    if len(color) != 6 or any(c not in HEX for c in color):
        raise ValueError(f"Color inválido: {color}; usa RRGGBB")
    if any(ch in parts[0] for ch in "{}"):
        remainder = SEGMENT.sub("", parts[0])
        if "{" in remainder or "}" in remainder:
            raise ValueError("Marcado de color inválido; usa {TEXTO|RRGGBB}")
        for match in SEGMENT.finditer(parts[0]):
            segment_text = match.group(0)[1:-1].rsplit("|", 1)[0].strip()
            if len(segment_text.split()) != 1:
                raise ValueError("Cada color de acento debe aplicarse a una sola palabra")
    if len(parts) > 3:
        raise ValueError("Formato inválido; usa TEXTO|COLOR|SIZE")
    size = int(parts[2]) if len(parts) > 2 and parts[2] else None
    if size is not None and size <= 0:
        raise ValueError("El tamaño de texto debe ser mayor que cero")
    return "|".join([parts[0], color] + ([str(size)] if size else []))


def normalize_block(value):
    if isinstance(value, str):
        value = value.splitlines()
    lines = [_line(x) for x in value if x and x.strip()]
    if not lines:
        raise ValueError("El bloque editorial no puede estar vacío")
    if len(lines) > MAX_LOGICAL_LINES_PER_BLOCK:
        raise ValueError(
            f"Máximo {MAX_LOGICAL_LINES_PER_BLOCK} líneas lógicas por bloque"
        )
    return lines


def _strip_diacritics(value):
    """Remove accents/diacritics while keeping the visible copy readable."""
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value or "")
        if not unicodedata.combining(ch)
    )


def _normalize_copy_line(line):
    """Uppercase a spec and remove accents without touching its color codes."""
    parts = _split_top_level(line)
    markup = parts[0]
    out, pos = [], 0
    for match in SEGMENT.finditer(markup):
        out.append(_strip_diacritics(markup[pos:match.start()]).upper())
        word = _strip_diacritics(match.group(0)[1:-1].rsplit("|", 1)[0]).upper()
        color = match.group(0).rsplit("|", 1)[-1].rstrip("}").lstrip("#").upper()
        out.append("{" + word + "|" + color + "}")
        pos = match.end()
    out.append(_strip_diacritics(markup[pos:]).upper())
    rebuilt = ["".join(out), parts[1] if len(parts) > 1 and parts[1] else "FFFFFF"]
    if len(parts) > 2 and parts[2]:
        rebuilt.append(parts[2])
    return "|".join(rebuilt)


def normalize_copy_block(value):
    """Normalize overlay copy to uppercase ASCII-like text with valid markup."""
    return [_normalize_copy_line(line) for line in normalize_block(value)]


def _accent_colors(lines):
    colors = set()
    for line in lines:
        parts = _split_top_level(line)
        line_color = (parts[1] if len(parts) > 1 and parts[1] else "FFFFFF")
        line_color = line_color.lstrip("#").upper()
        if line_color != "FFFFFF":
            colors.add(line_color)
        for match in SEGMENT.finditer(parts[0]):
            colors.add(match.group(0).rsplit("|", 1)[-1].rstrip("}").lstrip("#").upper())
    return colors


def _plain_line(line):
    """Devuelve el texto visible de una línea, sin marcado ni color."""
    text = _split_top_level(line)[0]
    return SEGMENT.sub(
        lambda match: match.group(0)[1:-1].rsplit("|", 1)[0], text
    )


def _fold_word(value):
    """Normaliza una palabra para comparar español/inglés sin acentos."""
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value or "")
        if not unicodedata.combining(ch)
    ).casefold()


def _accent_candidate_score(word):
    """Puntúa una palabra informativa; devuelve ``None`` para relleno."""
    folded = _fold_word(word)
    if not folded or folded in EDITORIAL_STOPWORDS or folded in EDITORIAL_WEAK_WORDS:
        return None
    if len(folded) <= 2 and folded not in IMPORTANT_SHORT_WORDS:
        return None
    score = 0
    if folded in IMPORTANT_TERMS or folded in IMPORTANT_SHORT_WORDS:
        score += 6
    if any(ch.isdigit() for ch in folded):
        score += 5
    if len(folded) >= 8:
        score += 2
    elif len(folded) >= 5:
        score += 1
    # The source may arrive in uppercase. Treat a long uppercase token as a
    # likely name/acronym, but do not let short function words through.
    if word.isupper() and len(folded) >= 3:
        score += 2
    return score


def _apply_word_accents(text, accents):
    """Insert ``{WORD|COLOR}`` without coloring surrounding punctuation."""
    if not accents:
        return text
    out, pos = [], 0
    for start, end, color in sorted(accents):
        if start < pos:
            continue
        out.append(text[pos:start])
        out.append("{" + text[start:end] + "|" + color + "}")
        pos = end
    out.append(text[pos:])
    return "".join(out)


def semantic_colorize_blocks(top, bottom, palette=None, max_highlights=4):
    """Color only important words in two editorial blocks.

    Existing ``{WORD|COLOR}`` segments are preserved. Plain lines use white as
    their base color and receive up to four deterministic word-level accents.
    The first picks are distributed between ARRIBA and ABAJO when both contain
    useful words; the remaining picks follow semantic relevance.
    """
    palette = tuple(palette or DEFAULT_ACCENT_PALETTE)
    palette = tuple(str(color).lstrip("#").upper() for color in palette)
    if not palette or any(len(color) != 6 or any(c not in HEX for c in color)
                          for color in palette):
        raise ValueError("La paleta editorial debe contener colores RRGGBB")
    max_highlights = max(0, int(max_highlights))
    blocks = [normalize_copy_block(top), normalize_copy_block(bottom)]
    candidates = []
    used_explicit = set()
    for block_index, lines in enumerate(blocks):
        for line_index, line in enumerate(lines):
            parts = _split_top_level(line)
            markup = parts[0]
            if SEGMENT.search(markup):
                for match in SEGMENT.finditer(markup):
                    used_explicit.add(
                        match.group(0).rsplit("|", 1)[-1]
                        .rstrip("}").lstrip("#").upper()
                    )
                continue
            for match in WORD.finditer(markup):
                score = _accent_candidate_score(match.group(0))
                if score is not None:
                    candidates.append({
                        "block": block_index,
                        "line": line_index,
                        "start": match.start(),
                        "end": match.end(),
                        "score": score,
                    })

    selected = []
    pools = {
        block: sorted(
            (item for item in candidates if item["block"] == block),
            key=lambda item: (-item["score"], item["line"], item["start"]),
        )
        for block in (0, 1)
    }
    # This gives the desired 1+3 or 2+2 distribution when the copy supports
    # it, without inventing accents in a block that has no useful words.
    for block in (0, 1):
        if pools[block] and len(selected) < max_highlights:
            selected.append(pools[block].pop(0))
    remaining = sorted(
        (item for pool in pools.values() for item in pool),
        key=lambda item: (-item["score"], item["block"], item["line"], item["start"]),
    )
    selected.extend(remaining[: max(0, max_highlights - len(selected))])

    by_line = {}
    for index, item in enumerate(selected):
        color = palette[index % len(palette)]
        by_line.setdefault((item["block"], item["line"]), []).append(
            (item["start"], item["end"], color)
        )
    result = []
    for block_index, lines in enumerate(blocks):
        colored_lines = []
        for line_index, line in enumerate(lines):
            parts = _split_top_level(line)
            markup = parts[0]
            accents = by_line.get((block_index, line_index), [])
            if not SEGMENT.search(markup):
                markup = _apply_word_accents(markup, accents)
                # A non-white whole-line color defeats the semantic rule; new
                # automatic proposals always use white as the base.
                base_color = "FFFFFF"
            else:
                base_color = parts[1] if len(parts) > 1 and parts[1] else "FFFFFF"
            rebuilt = [markup, base_color.lstrip("#").upper()]
            if len(parts) > 2 and parts[2]:
                rebuilt.append(parts[2])
            colored_lines.append("|".join(rebuilt))
        result.append(colored_lines)
    used = set(used_explicit)
    used.update(palette[index % len(palette)] for index, _ in enumerate(selected))
    return result[0], result[1], used


def apply_semantic_colors(proposal_set, palette=None, max_highlights=4):
    """Apply the automatic word-level color contract to every proposal."""
    for proposal in proposal_set.options:
        proposal.top, proposal.bottom, _used = semantic_colorize_blocks(
            proposal.top, proposal.bottom, palette=palette,
            max_highlights=max_highlights,
        )
        marks = []
        for line in proposal.top + proposal.bottom:
            for match in SEGMENT.finditer(_split_top_level(line)[0]):
                word = match.group(0)[1:-1].rsplit("|", 1)[0].strip()
                color = match.group(0).rsplit("|", 1)[-1].rstrip("}").lstrip("#").upper()
                if color != "FFFFFF":
                    marks.append(f"{word}={color}")
        proposal.color_notes = (
            "Acentos semánticos: " + ", ".join(marks)
            if marks else "Texto base blanco; no se encontraron palabras clave claras."
        )
    return proposal_set


def _validate_accent_words(lines):
    """Reject explicit markup that highlights a Spanish/English stopword."""
    for line in lines:
        parts = _split_top_level(line)
        for match in SEGMENT.finditer(parts[0]):
            segment_text = match.group(0)[1:-1].rsplit("|", 1)[0].strip()
            word = re.sub(r"[^\wÀ-ÿ'’\-]", "", segment_text)
            if _fold_word(word) in EDITORIAL_STOPWORDS:
                raise ValueError(f"No se debe colorear la palabra de relleno: {segment_text}")


def _title_key(lines):
    """Normaliza un bloque para detectar propuestas literalmente repetidas."""
    text = " ".join(_plain_line(line) for line in lines)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _validate_title_copy(lines):
    text = " ".join(_plain_line(line) for line in lines).strip()
    if not text:
        raise ValueError("El título editorial no puede estar vacío")
    if "#" in text or re.search(r"https?://|www\.", text, re.IGNORECASE):
        raise ValueError("El título no debe incluir hashtags ni URLs")
    normalized = re.sub(r"\s+", " ", text).casefold()
    for hook in GENERIC_HOOKS:
        if normalized == hook or normalized.startswith(hook + " "):
            raise ValueError(
                f"El título empieza con un gancho genérico no informativo: {hook}"
            )


@dataclass
class EditorialProposalSet:
    """Tres alternativas para un mismo VideoJob; solo una puede aprobarse."""
    job_path: str
    options: list[EditorialProposal] = field(default_factory=list)
    selected: int | None = None

    def validate(self):
        if not self.job_path:
            raise ValueError("Un set editorial debe estar asociado a un VideoJob")
        if len(self.options) != 3:
            raise ValueError("Un set editorial debe contener exactamente 3 opciones")
        for proposal in self.options:
            proposal.validate()
        source_urls = {proposal.source_url for proposal in self.options}
        if len(source_urls) != 1:
            raise ValueError("Las tres propuestas deben pertenecer al mismo origen")
        title_keys = [_title_key(option.top + option.bottom) for option in self.options]
        if len(set(title_keys)) != len(title_keys):
            raise ValueError("Las tres propuestas deben ser distintas entre sí")
        if self.selected is not None and not 0 <= self.selected < len(self.options):
            raise ValueError("Índice de opción editorial inválido")
        approved = [i for i, option in enumerate(self.options)
                    if option.status == "approved"]
        if self.selected is None and approved:
            raise ValueError("Una opción aprobada debe quedar registrada como seleccionada")
        if self.selected is not None and approved != [self.selected]:
            raise ValueError("El set editorial debe tener exactamente una opción aprobada")
        return self

    def choose(self, index):
        self.validate()
        if not 0 <= index < len(self.options):
            raise ValueError("Opción editorial inexistente")
        for proposal in self.options:
            proposal.status = "proposed"
        self.options[index].approve()
        self.selected = index
        return self.options[index]

    def save(self, path):
        self.validate()
        data = {"job_path": self.job_path, "selected": self.selected,
                "options": [asdict(option) for option in self.options]}
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(job_path=data["job_path"], selected=data.get("selected"),
                   options=[EditorialProposal(**o) for o in data["options"]])


@dataclass
class EditorialProposal:
    source_url: str
    original_title: str = ""
    original_description: str = ""
    author: str = ""
    language: str = "es"
    analysis: str = ""
    top: list[str] = field(default_factory=list)
    bottom: list[str] = field(default_factory=list)
    color_notes: str = ""
    status: str = "proposed"  # proposed | approved | rejected

    def validate(self):
        if not self.source_url:
            raise ValueError("La propuesta editorial necesita un origen")
        self.top = normalize_copy_block(self.top)
        self.bottom = normalize_copy_block(self.bottom)
        _validate_title_copy(self.top + self.bottom)
        _validate_accent_words(self.top + self.bottom)
        accents = _accent_colors(self.top + self.bottom)
        if len(accents) > MAX_ACCENT_COLORS:
            raise ValueError(
                f"Una propuesta puede usar como máximo {MAX_ACCENT_COLORS} "
                f"colores de acento; se encontraron {len(accents)}"
            )
        if self.status not in {"proposed", "approved", "rejected"}:
            raise ValueError("Estado editorial inválido")
        return self

    def approve(self):
        self.status = "approved"
        return self

    def to_specs(self):
        if self.status != "approved":
            raise PermissionError("La propuesta no está aprobada")
        self.validate()
        return "\n".join(self.top), "\n".join(self.bottom)

    def save(self, path):
        self.validate()
        Path(path).write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path):
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


def display(proposal):
    """Texto para Telegram. ORIGINAL y PROPUESTO se muestran antes de aprobar."""
    def visible(lines):
        return "\n".join("• " + _plain_line(x) for x in lines)
    return "\n".join([
        "ORIGINAL",
        proposal.original_title or "(sin título)",
        proposal.original_description or "",
        "",
        "ANÁLISIS",
        proposal.analysis or "(sin análisis editorial)",
        "",
        "PROPUESTO (ES)",
        "ARRIBA:\n" + visible(proposal.top),
        "ABAJO:\n" + visible(proposal.bottom),
        "",
        "COLOR: " + (proposal.color_notes or "palabras clave marcadas en el archivo de propuesta"),
        "",
        "Selecciona una de las tres opciones para aprobarla o indica qué texto/cambio quieres.",
    ]).strip()
