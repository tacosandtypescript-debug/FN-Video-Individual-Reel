# Fortnite Vertical Video Editor

Skill de edición vertical 9:16 para videos de Fortnite y noticias de X/Twitter.

## Incluye

- Resolución de videos con `yt-dlp`.
- Análisis con `ffprobe`.
- Fondo cover con blur, sin deformación.
- Gameplay central centrado y conservando proporción.
- Esquinas redondeadas y sombra suave.
- Firma `CODIGO: KHETZALGG` centrada abajo, como texto ligero.
- Texto superior e inferior con colores semánticos por palabra: solo se acentúan
  términos informativos, no palabras de relleno.
- Jerarquía automática: títulos cortos más grandes y texto de apoyo independiente.
- Ajuste duro de safe zone: wrapping, reducción y truncado con `…` antes de
  permitir cualquier desborde.
- Overlay normalizado en MAYÚSCULAS y sin tildes/diacríticos.
- Renderizado con FFmpeg y NVENC cuando hay NVIDIA, con fallback automático a
  `libx264` si el entorno no dispone de GPU.
- Validación de gaps, dimensiones, SAR, DAR, audio y tamaño.
- Preparación de copia compatible con Telegram.
- Flujo editorial con tres propuestas antes de renderizar.

## Dependencias

Requiere Python 3.11+, FFmpeg/FFprobe, `yt-dlp`, Pillow y NumPy. Consulta
`requirements.txt` para las dependencias Python. La GPU NVIDIA es opcional, pero
si está disponible el render usa `h264_nvenc`; de lo contrario usa el fallback
CPU configurado en el preset.

## Render básico

```bash
python3 scripts/render_video.py INPUT.mp4 -o SALIDA.mp4 \
  --preset tiktok_fortnite --top top.txt --bot bot.txt
```

Cada línea de `top.txt` o `bot.txt` usa el formato:

```text
TEXTO|COLOR_HEX|TAMAÑO_OPCIONAL
```

Para un video sin texto, se pueden usar archivos vacíos.

## Preparación para Telegram

```bash
python3 scripts/prepare_telegram.py SALIDA.mp4 -o SALIDA_tg.mp4
```

## Tests

```bash
cd references/tests
python3 -m unittest discover -p 'test_*.py' -v
```

## Bot de Telegram

La integración lista para montar está en `telegram_bot.py`. Usa
`python-telegram-bot` 22.x, crea una carpeta aislada por `job_id`, muestra tres
propuestas con botones inline y solo renderiza la opción aprobada. También
acepta `/video <URL>` y `/video` seguido de un MP4 adjunto.

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN='123456:token-de-BotFather'
python3 telegram_bot.py --jobs-dir /var/lib/fortnite-vve/jobs --max-renders 1
```

La guía de integración con un bot existente está en
`docs/TELEGRAM.md`. El proveedor incluido es conservador y usa únicamente
metadata de la fuente; para copy editorial en español se puede inyectar un
`ProposalProvider` propio sin modificar el motor FFmpeg.

## Documentación completa

Consulta `SKILL.md` y `references/rules/` para el flujo editorial, geometría,
zona segura, fondo, tipografía, render y validación. Las órdenes completas de
instalación y operación están en `docs/COMMANDS.md`.

## Licencia y origen

Skill de uso personal para el flujo de contenido de Isaac. Los scripts y
configuraciones pertenecen a este repositorio privado.
