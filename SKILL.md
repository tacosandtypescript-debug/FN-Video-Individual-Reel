---
name: vertical-video-editor
description: "Use when /video or vertical 9:16 video edit with FFmpeg."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [ffmpeg, vertical, video, tiktok, reels, geometria, cover, "/video"]
---

# Vertical Video Editor — Skill canonica de edicion de video vertical

Motor unico de edicion vertical 9:16. **Todo cambio de estilo futuro se hace AQUI**
y los videos nuevos heredan las reglas automaticamente. Entrada desde Telegram: `/video`.

## Cuando se activa

- El usuario envia `/video` (con o sin archivo adjunto) o pide editar un video vertical estilo TikTok/Reels.
- `/video` + archivo adjunto -> empieza de inmediato.
- `/video` sin archivo -> responder pidiendo el video y **mantener VIDEO_EDIT_MODE** en la conversacion; el siguiente archivo de ese chat se asocia al flujo.
- Parametros opcionales (estables): `/video preset=tiktok_fortnite`, `/video debug`, `/video gap=32`.

## Reglas obligatorias

1. **FFmpeg es el motor**: FFprobe (analisis) -> scripts de geometria (calculos) -> FFmpeg (composicion/render). Nunca sustituir FFmpeg por otro editor.
2. **Canvas vertical 9:16** (1080x1920 por defecto). Todos los calculos son RELATIVOS al canvas: sirven para otras resoluciones verticales.
3. **Video central**: conserva SIEMPRE su aspect ratio (nunca deformarlo), centrado, tamano calculado dinamicamente. Sus limites reales (`videoLeft/Top/Right/Bottom/Width/Height`) son el punto de referencia del layout.
4. **Textos anclados al video, NUNCA a Y fijas**: `topTextBottom = videoTop - gap`, `bottomTextTop = videoBottom + gap`, con `topGap == bottomGap`. Si un bloque tiene varias lineas, medir primero el bbox completo del bloque y posicionarlo como unidad.
5. **Background blur tipo cover, prohibido el stretch**: `scale=WxH:force_original_aspect_ratio=increase` -> `crop=WxH:(iw-W)/2:(ih-H)/2` -> `gblur`. Prohibido `scale=1080:1920` puro (deforma) y prohibido downscale extremo + upscale (destruye calidad). Blur moderado a resolucion final.
6. **FFprobe antes de editar**: width, height, DAR, SAR, rotation, duration, fps, pixel format; `cropdetect` si hay barras negras/letterbox (contenido util).
7. **Safe zones**: reservar areas seguras TikTok/Reels (botones laterales, @usuario, caption, controles). Las safe zones NO rompen la regla de textos pegados al video: si falta espacio, se desplaza el bloque entero lo minimo.
8. **Preset visual**: constantes configurables viven en `presets/tiktok_fortnite.json` (canvas, gap, blur, fuentes, spacing, safe zones, outline, animacion, encode). Prohibido numeros magicos en los scripts.

## Pipeline (scripts en `scripts/`)

```
probe_video.py        FFprobe: width/height/DAR/SAR/rotation/fps/duration/pix_fmt
  -> detect_geometry.py   cropdetect: imagen activa (quita barras)
  -> calculate_layout.py  video contain + bloques de texto (bbox) + gap simetrico
  -> build_background.py  cadena cover + crop centrado + gblur
  -> build_text_layout.py drawtext por linea (fuente/color/tamano del preset)
  -> build_ffmpeg_filter.py filter_complex completo (bg + fg + overlay + texto)
  -> render_video.py      CLI: preset + override por flag + render NVENC
  -> validate_render.py   mide gaps reales del frame y genera frame diagnostico
```

## Uso

```bash
python3 scripts/render_video.py INPUT.mp4 -o SALIDA.mp4 \
    --preset tiktok_fortnite \
    --top top.txt --bot bot.txt \       # cada linea: TEXTO|COLORHEX|SIZE(opcional)
    [--canvas 1080x1920] [--gap 32] [--blur 16] [--cq 21]
```

`top.txt`/`bot.txt`: una linea por linea de texto: `TEXTO|HEXCOLOR|SIZEpx` (SIZE opcional; por defecto el del preset). Las 2 lineas de arriba forman UN bloque; las de abajo, otro.

### Debug

- `--debug-layout`: imprime VIDEO ANALYSIS / CANVAS / FOREGROUND / TEXT / BACKGROUND.
- `--diagnostic-frame`: genera un PNG con bounding boxes, videoTop/Bottom, gaps y safe zones dibujadas.

## Verificacion (no opcional)

Tras renderizar, `validate_render.py` mide sobre el frame real: si `gap_real_arriba` o `gap_real_abajo` difieren >2px del modelo, corrige el layout y re-renderiza (max 3 intentos). El render se considera OK con gaps reales == modelo (±2px) y zona segura respetada.

## Telegram /video

1. Llega `/video` (o `/video preset=...`). Cargar esta skill y seguir el pipeline.
2. Si no hay archivo: `VIDEO_EDIT_MODE = true` en la conversacion; pedir el video. El proximo archivo del chat entra al flujo.
3. Con el archivo: guardarlo, `probe` -> geometria -> preset -> textos (preguntar titulo si no viene) -> render -> validar -> **enviar el video terminado por Telegram**.
4. Entregar SIEMPRE primero un frame de aprobacion si el usuario lo pide; ante duda, frame primero.

## Tests

```bash
cd <skill_dir>/references/tests && python3 -m unittest discover -s . -p 'test_*.py' -v
```

## Relacion con otras skills

- `fortnite-tiktok-noticias`: usa este motor para sus renders (noticias). Mantiene su flujo editorial (guiones/captions/fuentes X) pero la composicion de video la hace `vertical-video-editor`.
- `tiktok-video-editing` y `video-short-text-overlay`: LEGACY, no usar para renders nuevos; redirigir aqui.
