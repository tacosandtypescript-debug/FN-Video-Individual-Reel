# Changelog

Todos los cambios relevantes de este proyecto. Formato basado en
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Sin publicar]

### Cambios
- Reorganización del repositorio: `telegram_bot.py` pasa a `scripts/` y la
  batería de pruebas pasa a `tests/` en la raíz, con sus rutas actualizadas en
  `SKILL.md`, `README.md` y `docs/`.
- `.gitignore` ampliado (entornos virtuales, secretos, renders, cachés de
  herramientas y archivos de sistema).
- Añadidos `LICENSE` (MIT) y este `CHANGELOG.md`.
- Documentación con índice de estructura del proyecto.
- Dependencias Python acotadas por versión y `yt-dlp` incluido en
  `requirements.txt`.
- Añadido `scripts/check_installation.py` para validar runtime, comandos,
  fuente y preset antes de operar.
- `validate_render.py` ahora ofrece una CLI documentada para validar una salida
  sin depender de imports internos.
- Validación de duración completa del render, canvas estrictamente 9:16 y
  limpieza de salidas inválidas.
- Miniaturas de Telegram convertidas a JPEG compatible (máximo 320 px y menos
  de 200 kB), además de hashtag en el caption.
- Descargas remotas limitadas por tamaño y bloqueadas para hosts locales o no
  globales; rutas de proyecto/presets corregidas para instalaciones portables.

## 2026-09-11

### Cambios
- El repositorio queda con una sola rama, `main`, que es además la rama por
  defecto.
- Repositorio renombrado a `FN-Video-Individual-Reel`.

## 2026-09-10

### Añadido
- Verificación obligatoria de render completo antes de entregar: se compara la
  duración del render con la del original (±0.1 s) y se comprueba que `ffprobe`
  lea el contenedor, para no enviar MP4 truncados.

## 2026-09-07

### Añadido
- Integración de Telegram lista para montar (`telegram_bot.py`), con carpeta
  aislada por `job_id`, propuestas con botones inline, límite de renders
  concurrentes y entrega con `sendVideo` (caption + miniatura).
- `docs/TELEGRAM.md` con la guía de montaje.

### Cambios
- Mejoras de layout, geometría, tipografía, safe zones y validación de codificación.
- La batería de pruebas pasa de 32 a 48 pruebas.

## 2026-09-03

### Añadido
- Soporte de trabajos concurrentes: cada video usa su propio `job_id`, carpeta,
  textos, propuesta, render y entrega, permitiendo hasta tres trabajos sin que
  uno interfiera con otro.

## 2026-09-02

### Añadido
- Motor de edición vertical 9:16 con FFmpeg: `probe_video` → `detect_geometry` →
  `calculate_layout` → `build_background` → `build_text_layout` →
  `build_ffmpeg_filter` → `render_video` → `prepare_telegram`.
- Fondo cover con blur, video centrado sin deformar, esquinas redondeadas y
  sombra suave.
- Textos anclados al video con gaps simétricos y color semántico por palabra.
- Auto-tamaño para textos cortos y ajuste duro de zona segura.
- Flujo editorial: `ORIGINAL` + `ANÁLISIS` + tres propuestas en español y
  aprobación explícita antes de renderizar.
- Preparación de copia compatible con Telegram (720×1280, SAR 1:1, DAR 9:16).
- Preset `tiktok_fortnite` con todos los parámetros visuales.
