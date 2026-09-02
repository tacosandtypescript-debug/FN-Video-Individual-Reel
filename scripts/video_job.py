#!/usr/bin/env python3
"""video_job.py - Objeto de trabajo del flujo /video <URL>."""
import json, os
from dataclasses import dataclass, field, asdict


@dataclass
class VideoJob:
    source_url: str = ""
    resolved_url: str = ""
    platform: str = ""
    title: str = ""
    description: str = ""
    author: str = ""
    duration: float = 0.0
    thumbnail: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    date: str = ""
    input_file: str = ""
    workdir: str = ""
    metadata: dict = field(default_factory=dict)

    def save(self, path=None):
        path = path or os.path.join(self.workdir or ".", "video_job.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, ensure_ascii=False, indent=2)
        return path

    def summary(self):
        lines = [
            f"Plataforma: {self.platform}",
            f"Titulo: {self.title or '(sin titulo)'}",
            f"Autor: {self.author or '-'}",
            f"Duracion: {self.duration:.1f}s",
            f"Resolucion: {self.width}x{self.height}",
            f"Archivo: {self.input_file}",
        ]
        if self.description:
            lines.append(f"Descripcion: {self.description[:120]}")
        return "\n".join(lines)
