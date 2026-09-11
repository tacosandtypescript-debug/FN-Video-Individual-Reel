#!/usr/bin/env python3
"""Check the local runtime required by the vertical-video editor."""
from __future__ import annotations

import importlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"
PRESET_PATH = PROJECT_ROOT / "references" / "presets" / "tiktok_fortnite.json"
REQUIRED_DISTRIBUTIONS = (
    ("Pillow", "PIL"),
    ("numpy", "numpy"),
    ("python-telegram-bot", "telegram"),
)
REQUIRED_COMMANDS = ("ffmpeg", "ffprobe", "yt-dlp")


def _version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "missing"


def _command_version(command: str) -> str:
    path = shutil.which(command)
    if not path:
        return "missing"
    try:
        version_flag = "--version" if command == "yt-dlp" else "-version"
        result = subprocess.run(
            [path, version_flag], capture_output=True, text=True,
            timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    first_line = (result.stdout or result.stderr).splitlines()
    return first_line[0].strip() if first_line else "unavailable"


def _check_preset() -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(PRESET_PATH.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return [f"preset inválido: {exc}"]
    canvas = data.get("canvas")
    if (not isinstance(canvas, list) or len(canvas) != 2 or
            not all(isinstance(value, int) and value > 0 for value in canvas) or
            canvas[0] * 16 != canvas[1] * 9):
        errors.append("el preset no define un canvas 9:16 válido")
    for key in ("font", "safe", "encode"):
        if key not in data:
            errors.append(f"falta la clave {key!r} en el preset")
    encode = data.get("encode", {})
    for key in ("vcodec", "cpu_vcodec", "pix_fmt", "acodec"):
        if key not in encode:
            errors.append(f"falta encode.{key!r} en el preset")
    return errors


def main() -> int:
    errors: list[str] = []
    if sys.version_info < (3, 11):
        errors.append(
            f"Python {sys.version_info.major}.{sys.version_info.minor} encontrado; "
            "se requiere Python 3.11 o superior"
        )
    else:
        print(f"OK Python: {sys.version.split()[0]}")

    for distribution, module_name in REQUIRED_DISTRIBUTIONS:
        installed = _version(distribution)
        if installed == "missing":
            errors.append(f"falta la dependencia Python {distribution}")
            continue
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - depends on local install
            errors.append(f"no se puede importar {module_name}: {exc}")
            continue
        print(f"OK Python package: {distribution} {installed}")

    for command in REQUIRED_COMMANDS:
        version = _command_version(command)
        if version in {"missing", "unavailable"}:
            errors.append(f"falta o no responde el comando {command}")
        else:
            print(f"OK command: {command} ({version})")

    errors.extend(_check_preset())
    if not errors:
        sys.path.insert(0, str(SCRIPTS))
        try:
            import render_video

            font = render_video.resolve_font(
                json.loads(PRESET_PATH.read_text(encoding="utf-8"))["font"]
            )
            print(f"OK font: {font}")
        except Exception as exc:
            errors.append(f"no se pudo resolver la fuente del preset: {exc}")

    encoder_line = _command_version("ffmpeg")
    if encoder_line != "missing":
        try:
            result = subprocess.run(
                [shutil.which("ffmpeg") or "ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if "h264_nvenc" in (result.stdout + result.stderr):
                print("INFO optional encoder: h264_nvenc disponible")
            else:
                print("INFO optional encoder: NVENC no disponible; se usará libx264")
        except (OSError, subprocess.TimeoutExpired):
            print("INFO optional encoder: no se pudo comprobar NVENC")

    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    print("Instalación válida: el runtime requerido está disponible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
