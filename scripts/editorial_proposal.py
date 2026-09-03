#!/usr/bin/env python3
"""editorial_proposal.py - Contrato editorial entre /video y el render.

No traduce ni inventa contexto: el agente analiza titulo/descripcion y crea una
propuesta en español. Este modulo persiste la propuesta, valida colores y evita
que FFmpeg reciba texto sin aprobación explícita.
"""
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

HEX = "0123456789ABCDEF"


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
    size = int(parts[2]) if len(parts) > 2 and parts[2] else None
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
        "PROPUESTO (ES)",
        "ARRIBA:\n" + visible(proposal.top),
        "ABAJO:\n" + visible(proposal.bottom),
        "",
        "COLOR: " + (proposal.color_notes or "palabras clave marcadas en el archivo de propuesta"),
        "",
        "Responde ‘sí’ para renderizar o indica qué texto/cambio quieres.",
    ]).strip()
