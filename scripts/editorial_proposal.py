#!/usr/bin/env python3
"""editorial_proposal.py - Contrato editorial entre /video y el render.

No traduce ni inventa contexto: el agente analiza titulo/descripcion y crea una
propuesta en español. Este modulo persiste la propuesta, valida colores y evita
que FFmpeg reciba texto sin aprobación explícita.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict, field
from pathlib import Path

HEX = "0123456789ABCDEF"
SEGMENT = re.compile(r"\{[^{}|]+\|#?[0-9A-Fa-f]{6}\}")
MAX_ACCENT_COLORS = 3
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
    if len(lines) > 2:
        raise ValueError("Máximo dos líneas por bloque")
    return lines


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
        if len(self.options) != 3:
            raise ValueError("Un set editorial debe contener exactamente 3 opciones")
        for proposal in self.options:
            proposal.validate()
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
        self.top = normalize_block(self.top)
        self.bottom = normalize_block(self.bottom)
        _validate_title_copy(self.top + self.bottom)
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
        return "\n".join("• " + x.split("|")[0].replace("{", "").replace("}", "") for x in lines)
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
