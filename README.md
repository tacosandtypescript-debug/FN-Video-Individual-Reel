# Fortnite Vertical Video Editor

Skill de edición vertical 9:16 para videos de Fortnite y noticias de X/Twitter.

## Incluye

- Resolución de videos con `yt-dlp`.
- Análisis con `ffprobe`.
- Fondo cover con blur, sin deformación.
- Gameplay central centrado y conservando proporción.
- Esquinas redondeadas y sombra suave.
- Texto superior e inferior con colores por segmento.
- Tamaño automático para textos cortos.
- Renderizado con FFmpeg y NVENC cuando hay NVIDIA.
- Validación de gaps, dimensiones, SAR, DAR, audio y tamaño.
- Preparación de copia compatible con Telegram.
- Flujo editorial con tres propuestas antes de renderizar.

## Dependencias

Requiere Python 3.11+, FFmpeg/FFprobe, `yt-dlp`, Pillow y NumPy. Consulta
`requirements.txt` para las dependencias Python. La GPU NVIDIA es opcional, pero
si está disponible el render usa `h264_nvenc`.

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

## Documentación completa

Consulta `SKILL.md` y `references/rules/` para el flujo editorial, geometría,
zona segura, fondo, tipografía, render y validación.

## Licencia y origen

Skill de uso personal para el flujo de contenido de Isaac. Los scripts y
configuraciones pertenecen a este repositorio privado.
