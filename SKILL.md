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

## Flujo editorial obligatorio — antes de CUALQUIER render

`/video <URL>` **NO autoriza renderizar directamente**. Tras resolver y descargar,
el agente debe analizar UNA sola publicación (título, descripción, autor, fecha y
el video descargado si aporta contexto) y preparar una propuesta editorial.

1. Mostrar siempre, en este orden:
   - **ORIGINAL**: título y descripción tal como fueron publicados (EN o ES).
   - **ANÁLISIS**: qué comunica realmente el post y el video; interpretar el
     contexto antes de escribir, sin copiar/traducir literalmente ni inventar.
   - **3 PROPUESTAS (ES)**, independientes, naturales y noticiosas. Cada una
     tiene por defecto un bloque **ARRIBA** y otro **ABAJO** (1–2 líneas por
     bloque). La lectura ARRIBA + ABAJO debe formar una idea completa:
     **arriba nombra el hecho principal y abajo añade el dato que lo completa**
     (qué cambia, cuándo, dónde o para quién). Está prohibido reformular el
     mismo título dos veces, intercambiar palabras sin sentido o usar frases
     que no se entiendan aisladas. Antes de mostrarlas, comprobar: (a) se
     entienden en español natural, (b) son fieles a la publicación, (c) no
     repiten la misma información y (d) el gancho no es clickbait falso.
     Solo ofrecer un bloque único si el post de verdad no necesita contexto extra.
   - **COLORES**: anotar solo palabras/frases informativas con marcado por
     segmento: `REGRESA LA {TEMPORADA X|B84DFF}|FFFFFF`. Lo que esté entre `{}`
     aplica color solo a esa palabra/frase; el color final de la línea es el
     color por defecto del resto. Elegir color por significado: nombre/evento,
     novedad, fecha o dato clave. Nunca pintar toda la línea sin razón ni usar
     color como decoración.
2. Presentar las tres opciones como botones inline de Telegram mediante
   `clarify` (una sola pregunta, elecciones: **OPCIÓN 1**, **OPCIÓN 2**,
   **OPCIÓN 3**). El texto previo debe mostrar arriba/abajo y las palabras de
   color de cada opción. No sustituir botones por un “elige un número” si la
   plataforma soporta botones.
3. Al tocar un botón, persistir `EditorialProposalSet` con exactamente tres
   alternativas y llamar `choose(indice)`: la seleccionada obtiene
   `status=approved`; las otras permanecen `proposed`. Solo la seleccionada se
   pasa a `render-approved`. Si el usuario pide cambios, crear/mostrar de nuevo
   tres opciones y volver a esperar su botón.

Herramientas persistentes:

```text
video_command.py prepare URL --workdir JOB_DIR --job JOB_DIR/video_job.json
# resolver + descargar + metadata, sin FFmpeg

editorial_proposal.py
# valida y guarda bloques arriba/abajo con color

video_command.py render-approved --job JOB.json --proposal PROPUESTA.json -o salida.mp4
# rechaza propuestas con status distinto de approved
```

El handler Telegram se limita a orquestar esas dos fases y conservar la ruta del
Job/Proposal por chat. No contiene FFmpeg ni la lógica editorial.

## Telegram /video <URL> — one-shot (flujo oficial)

El comando principal es **`/video <URL>`** y significa:
_"Obtén este video, reúne su información, cierra las herramientas de descarga y
edítalo automáticamente usando todas las reglas de vertical-video-editor."_

Flujo (handler de Telegram SOLO orquesta; la lógica vive en los scripts):

```
/video URL
  1 validar y resolver con `video_command.py prepare` (yt-dlp primero)
  2 descargar y guardar VideoJob + metadata
  3 analizar publicación y mostrar ORIGINAL + PROPUESTO (ES), arriba/abajo/colores
  4 ESPERAR aprobación explícita del usuario
  5 `video_command.py render-approved` -> probe -> geometría -> preset -> FFmpeg -> validar
  6 enviar video terminado por Telegram (MEDIA:<out>)
```

El navegador sigue siendo solo fallback de la fase 1; debe cerrarse por completo
antes de la fase 3 y jamás permanece abierto durante FFmpeg.

Ejecución desde línea: `python3 scripts/video_command.py run URL -o out.mp4`
(mensajes de progreso: Resolviendo… Descargando… Analizando… Preparando…
Renderizando… Validando… Enviando…).

### VideoJob (objeto de trabajo)

`source_url, resolved_url, platform, title, author, description, duration,
thumbnail, width, height, fps, date, input_file, workdir, metadata` — se guarda
como JSON junto a la salida. Si falta `--top/--bot`, el texto superior se genera
automáticamente desde el título (2 líneas que caben en el canvas); si no hay
título, pedir al usuario el texto antes de renderizar.

### Errores (siempre limpiar con try/finally)

URL inválida · plataforma no soportada · video privado · login requerido ·
descarga fallida · archivo vacío/corrupto · FFprobe fallido · FFmpeg fallido ·
timeout. En cualquier caso: cerrar navegador, matar procesos hijos, borrar
temporales y liberar el job.

### Compatibilidad

TikTok, X/Twitter, YouTube, Instagram y URLs directas MP4 vía yt-dlp (fallback
de navegador solo si realmente hace falta).

## Tests

```bash
cd <skill_dir>/references/tests && python3 -m unittest discover -s . -p 'test_*.py' -v
```

## Relacion con otras skills

- `fortnite-tiktok-noticias`: usa este motor para sus renders (noticias). Mantiene su flujo editorial (guiones/captions/fuentes X) pero la composicion de video la hace `vertical-video-editor`.
- `tiktok-video-editing` y `video-short-text-overlay`: LEGACY, no usar para renders nuevos; redirigir aqui.
