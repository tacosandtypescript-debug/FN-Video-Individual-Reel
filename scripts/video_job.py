#!/usr/bin/env python3
"""video_job.py - Objeto de trabajo del flujo /video <URL>."""
import json, os, tempfile
from dataclasses import dataclass, field, asdict


@dataclass
class VideoJob:
    job_id: str = ""
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
        parent = os.path.dirname(os.path.abspath(path)) or "."
        os.makedirs(parent, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".video_job.", suffix=".json", dir=parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(asdict(self), fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        return path

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as fh:
            return cls(**json.load(fh))

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
