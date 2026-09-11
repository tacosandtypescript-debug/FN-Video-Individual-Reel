# Órdenes completas de la skill

Todas las órdenes se ejecutan desde la carpeta raíz de esta skill.

## 1. Instalación

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/check_installation.py
```

Dependencias del sistema:

```bash
ffmpeg -version
ffprobe -version
```

`h264_nvenc` es opcional. Si no está disponible, el render usa `libx264`.
`check_installation.py` comprueba también que el ejecutable `yt-dlp` creado por
la instalación Python esté disponible en el `PATH`.

## 2. Preparar un enlace de X, TikTok, YouTube o Instagram

La preparación descarga y analiza el video, pero no renderiza ni publica:

```bash
python3 scripts/video_command.py prepare \
  "URL" \
  --workdir /ruta/jobs/ID/editorial_job \
  --job /ruta/jobs/ID/editorial_job/video_job.json
```

El trabajo genera `video_job.json` y `original.mp4`. Cada video debe usar un
`workdir` diferente; nunca reutilices la carpeta de otro trabajo.

## 3. Crear la propuesta editorial

Una propuesta aprobada usa bloques independientes. Cada línea tiene este formato:

```text
TEXTO|FFFFFF
TEXTO CON {PALABRA|00E5FF}|FFFFFF
```

El marcado de color solo puede aplicarse a una palabra. El archivo de propuesta
debe tener `status: approved` para poder renderizarse. El bot aplica la paleta
semántica del preset (hasta cuatro acentos) únicamente a palabras informativas;
artículos, preposiciones y conjunciones permanecen blancas. Si una línea supera
la safe zone, el renderer la envuelve, reduce o trunca con `…` antes de dibujarla.

## 4. Renderizar una propuesta aprobada

```bash
python3 scripts/video_command.py render-approved \
  --job /ruta/jobs/ID/editorial_job/video_job.json \
  --proposal /ruta/jobs/ID/editorial_job/selected_proposal.json \
  -o /ruta/jobs/ID/editorial_job/video_final.mp4
```

El render usa el preset `tiktok_fortnite`, fondo blur cover, video central sin
deformar, esquinas redondeadas, sombra suave, firma `CODIGO: KHETZALGG` como
texto ligero centrado abajo y textos anclados al video.

## 5. Render directo con archivos de texto

```bash
python3 scripts/render_video.py INPUT.mp4 \
  -o SALIDA.mp4 \
  --preset tiktok_fortnite \
  --top top.txt \
  --bot bot.txt \
  --debug-layout
```

Para un video sin texto, `top.txt` y `bot.txt` pueden estar vacíos.

## 6. Preparar una copia para Telegram

```bash
python3 scripts/prepare_telegram.py \
  video_final.mp4 \
  -o video_final_tg.mp4
```

La orden conserva el maestro si cumple las condiciones. Si hace falta, genera
una copia 720x1280, SAR 1:1, DAR 9:16, con audio compatible y tamaño reducido.
El pipeline del bot crea además una miniatura JPEG de máximo 320 px y menos de
200 kB, compatible con `send_video`.

## 7. Validar un render

```bash
python3 scripts/validate_render.py \
  video_final.mp4 \
  --canvas 1080x1920
```

Para exigir que la salida conserve una duración conocida, añade
`--expected-duration SEGUNDOS`.

También se puede inspeccionar la fuente antes del render:

```bash
python3 scripts/probe_video.py INPUT.mp4
python3 scripts/detect_geometry.py INPUT.mp4
```

## 8. Tests

```bash
python3 -m unittest discover \
  -s tests \
  -p 'test_*.py' \
  -v
```

## 9. Varios videos simultáneos

Usa una carpeta única por video:

```text
jobs/video-a/editorial_job/
jobs/video-b/editorial_job/
jobs/video-c/editorial_job/
```

Las descargas y análisis pueden avanzar en paralelo. Los renders pueden
limitarse a un máximo de tres según CPU, memoria y GPU. No compartas
`top.txt`, `bot.txt`, miniaturas, captions ni salidas entre trabajos.

## 10. Archivos principales

- `SKILL.md`: contrato completo y reglas editoriales.
- `README.md`: instalación y uso rápido.
- `references/presets/tiktok_fortnite.json`: estilo y parámetros.
- `references/rules/`: reglas de fondo, layout, render, safe zones y tipografía.
- `scripts/`: resolver, análisis, propuesta, geometría, render, validación y bot.
- `scripts/check_installation.py`: diagnóstico de dependencias, comandos, fuente y preset.
- `scripts/telegram_bot.py`: adaptador de Telegram (propuestas y entrega).
- `tests/`: batería automática.
- `docs/`: órdenes completas y guía de Telegram.
- `CHANGELOG.md` / `LICENSE`: historial de cambios y licencia MIT.
- `requirements.txt`: dependencias Python y de sistema documentadas.
