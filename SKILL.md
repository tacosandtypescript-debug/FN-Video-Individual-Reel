---
name: vertical-video-editor
description: "Use when /video or vertical 9:16 video edit with FFmpeg."
license: MIT
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
8. **Preset visual**: constantes configurables viven en `presets/tiktok_fortnite.json` (canvas, gap, blur, fuentes, spacing, safe zones, outline, animación, encode y acabado del primer plano). Prohibido usar números mágicos en los scripts.
9. **Video en primer plano**: aplicar esquinas ligeramente redondeadas y una
   sombra exterior suave para separarlo del background. No dibujar línea, marco ni
   borde visible. El radio, desplazamiento, blur y opacidad viven en el preset;
   deben mantenerse sutiles y no alterar la geometría ni deformar el video.
10. **Tamaño dinámico y safe zone dura**: cuando el texto sea corto, aumentar
    automáticamente el bloque superior hasta aproximadamente el 82% del ancho
    seguro, con máximo de 84 px a 1080×1920. El bloque inferior funciona como
    apoyo y puede tener un máximo menor (68 px en el preset Fortnite). Si una
    línea es larga, se mide con la fuente real, se parte por palabras y se reduce
    gradualmente hasta el mínimo del preset. Si todavía no cabe, se trunca con
    `…`; nunca se permite que el bbox ni el borde del texto crucen la safe zone.
    Un `SIZE` explícito es una preferencia visual, no puede romper este límite.
11. **Jerarquía de copy**: ARRIBA es el titular (hecho/acción principal) y ABAJO
    es el dato que lo completa (resultado, contexto o condición). Con poco texto,
    ARRIBA debe verse claramente más grande; con más texto, se reduce o se envuelve
    de forma independiente. El vídeo se encoge solo dentro del espacio que queda,
    conservando su aspect ratio y los gaps al texto.
12. **Color semántico por palabra**: el texto base es `FFFFFF` y cada segmento de
    acento debe marcar exactamente una palabra con `{PALABRA|RRGGBB}`. Usar hasta
    cuatro acentos de la paleta `B84DFF`, `42E8FF`, `FFDD00`, `FF39D7` (normalmente
    3–4 si hay suficientes palabras importantes); distribuirlos entre ARRIBA y
    ABAJO cuando ambos tengan contenido. No colorear palabras funcionales o de
    relleno como `de`, `del`, `la`, `el`, `en`, `y`, `o`, `que`, `es`, `un`, `una`,
    `para`, `por`, `con`, `a`, `the`, `of`, `in`, `and`, `is`, `to` o `for`. No
    colorear frases de varias palabras ni líneas completas por decoración. Si no
    hay una palabra importante clara, dejarla blanca.
13. **Copy del overlay**: todo texto que se dibuja sobre el vídeo —titular,
    apoyo y firma— se normaliza a MAYÚSCULAS y sin tildes/diacríticos. Ejemplo:
    `Código: khetzalgg` se renderiza como `CODIGO: KHETZALGG`; el campo
    **ORIGINAL** mostrado en la revisión sí conserva el texto publicado.

## Pipeline (scripts en `scripts/`)

```
probe_video.py        FFprobe: width/height/DAR/SAR/rotation/fps/duration/pix_fmt
  -> detect_geometry.py   cropdetect: imagen activa (quita barras)
  -> calculate_layout.py  video contain + bloques de texto (bbox) + gap simetrico
  -> build_background.py  cadena cover + crop centrado + gblur
  -> build_text_layout.py drawtext por linea (fuente/color/tamano del preset)
  -> build_ffmpeg_filter.py filter_complex completo (bg + fg + overlay + texto)
  -> render_video.py      CLI: preset + override por flag + render NVENC/CPU
  -> prepare_telegram.py  comprueba tamaño/DAR/SAR/audio y crea copia Telegram si hace falta
```

## Uso

```bash
python3 scripts/render_video.py INPUT.mp4 -o SALIDA.mp4 \
    --preset tiktok_fortnite \
    --top top.txt --bot bot.txt \       # cada linea: TEXTO|COLORHEX|SIZE(opcional)
    [--canvas 1080x1920] [--gap 32] [--blur 16] [--cq 21]
```

`top.txt`/`bot.txt`: una linea por linea de texto: `TEXTO|HEXCOLOR|SIZEpx` (SIZE opcional; por defecto el del preset). Se recomiendan 1–2 líneas lógicas por bloque; el renderer puede envolverlas en más líneas visuales para respetar la safe zone y recortar con `…` solo como último recurso. Las líneas de arriba forman UN bloque; las de abajo, otro.

### Debug

- `--debug-layout`: imprime VIDEO ANALYSIS / CANVAS / FOREGROUND / TEXT / BACKGROUND.
- `--diagnostic-frame`: genera un PNG con bounding boxes, videoTop/Bottom, gaps y safe zones dibujadas.

## Preparación para Telegram

```bash
python3 scripts/prepare_telegram.py RENDER.mp4 -o RENDER_tg.mp4
```

Si el archivo pesa como máximo 45 MB, lo conserva. Si supera ese tamaño, genera
una copia 720×1280 con `setsar=1`, DAR 9:16, audio AAC y NVENC (o libx264 si no
hay GPU). Después verifica
codec streams, dimensiones, SAR, proporción, duración y tamaño antes de entregar.
El archivo maestro no se modifica.


Tras renderizar, `validate_render.py` mide sobre el frame real: si `gap_real_arriba` o `gap_real_abajo` difieren >2px del modelo, corrige el layout y re-renderiza (max 3 intentos). El render se considera OK con gaps reales == modelo (±2px) y zona segura respetada.

**Verificación de render completo (obligatoria antes de enviar)**: un render cortado
por timeout, reinicio del gateway o cierre de la sesión deja un MP4 truncado o sin
`moov atom`, aunque pese decenas de MB. Antes de enviar cualquier video, comparar su
duración con la del original (±0.1 s) y comprobar que `ffprobe` lee el contenedor.
Si la duración es menor o el probe falla, borrar el archivo y repetir el render; los
renders largos (>30 s de video) deben lanzarse en segundo plano y no darse por
buenos solo por el peso del archivo.

## Procesamiento de varios videos a la vez

Cada video recibido debe crear un trabajo independiente, identificado por su
`job_id` y su propia carpeta. Nunca reutilizar rutas, `top.txt`, `bot.txt`,
`VideoJob`, propuestas, renders, miniaturas o captions de otro trabajo.

```
video A -> jobs/<id-A>/ -> propuesta A -> render A -> entrega A
video B -> jobs/<id-B>/ -> propuesta B -> render B -> entrega B
video C -> jobs/<id-C>/ -> propuesta C -> render C -> entrega C
```

Mientras un render está activo, se puede resolver otro enlace, extraer sus
fotogramas, analizarlo y mostrar sus tres propuestas. La respuesta de cada
aprobación debe conservar el `job_id` correspondiente; aprobar A nunca puede
renderizar B. Los procesos en segundo plano deben escribir cada salida en su
propia carpeta y devolver el resultado con su identificador.

Se permiten hasta tres trabajos simultáneos si los recursos lo permiten. Si
varios renders compiten por la GPU, mantener las fases de descarga/análisis en
paralelo y limitar solo el número de renders concurrentes para evitar saturar
VRAM; eso no debe bloquear la recepción ni la revisión editorial de los demás
videos. Telegram debe enviar cada MP4 solo cuando el resultado de ese mismo
`job_id` esté validado.


`/video <URL>` **NO autoriza renderizar directamente**. Tras resolver y descargar,
el agente debe analizar UNA sola publicación (título, descripción, autor, fecha y
el video descargado si aporta contexto) y preparar una propuesta editorial.

### Método para proponer títulos

Antes de redactar, separar la publicación en cuatro datos: **hecho** (qué ocurre),
**mecánica** (cómo ocurre), **resultado** (qué consigue el jugador) y **contexto**
(mapa, modo, fecha o condición). Si un dato no está confirmado por el post o el
video, no convertirlo en una afirmación.

Las tres propuestas deben tener ángulos editoriales realmente distintos:

- **RESULTADO**: el beneficio o efecto cuantificable para el jugador.
- **MECÁNICA**: la acción o elemento que explica cómo sucede.
- **CONTEXTO/NOVEDAD**: dónde ocurre, en qué modo o por qué es relevante ahora.

No hacer tres versiones con sinónimos del mismo título. Cada opción debe poder
publicarse por separado y ARRIBA + ABAJO debe leerse como una sola frase natural.
Usar un verbo concreto y un dato específico. Como guía visual, buscar 3–7 palabras
por línea, una idea principal por bloque y cero relleno.

Evitar comienzos y adjetivos vacíos como `MIRA`, `INCREÍBLE`, `BRUTAL`, `NO TE LO
PIERDAS`, `EL MEJOR`, `SECRETO`, `VIRAL` u `OMG`, salvo que sean parte de una cita o
de un hecho verificable. No copiar el titular original, traducirlo literalmente,
añadir hashtags, repetir `Fortnite` sin necesidad ni prometer un resultado que la
fuente no demuestra.

Ejemplo de estructura correcta para el caso de XP:

```text
OPCIÓN 1 — RESULTADO
ARRIBA: SUBE {5|B84DFF} NIVELES DE XP|FFFFFF
ABAJO: EN UNA SOLA PARTIDA|FFFFFF

OPCIÓN 2 — MECÁNICA
ARRIBA: ROMPE {ESTRUCTURAS|FFDD00}|FFFFFF
ABAJO: CON GRANADAS DE ONDA DE CHOQUE|FFFFFF

OPCIÓN 3 — CONTEXTO/NOVEDAD
ARRIBA: NUEVO {GLITCH|42E8FF} DE XP|FFFFFF
ABAJO: EN REALITY'S REIGN|FFFFFF
```

Antes de mostrar las opciones, hacer una lectura de control: quitar cada bloque
por separado, leerlo en voz alta, comprobar que no falta el sujeto o el verbo,
confirmar el dato contra ORIGINAL/ANÁLISIS y verificar que las tres opciones no
repiten la misma promesa.

1. Mostrar siempre, en este orden:
   - **ORIGINAL**: título y descripción tal como fueron publicados (EN o ES).
   - **ANÁLISIS**: qué comunica realmente el post y el video; resumir hecho,
     mecánica, resultado y contexto antes de escribir, sin copiar/traducir
     literalmente ni inventar. Si el video no permite confirmar una afirmación,
     indicarlo y redactar el título con el nivel de certeza disponible.
   - **3 PROPUESTAS (ES)**, independientes, naturales y noticiosas. Cada una
     tiene por defecto un bloque **ARRIBA** y otro **ABAJO** (1–2 líneas por
     bloque). La lectura ARRIBA + ABAJO debe formar una idea completa:
     **arriba nombra el hecho principal y abajo añade el dato que lo completa**
     (qué cambia, cuándo, dónde o para quién). Aplicar los tres ángulos RESULTADO,
     MECÁNICA y CONTEXTO/NOVEDAD definidos arriba. Está prohibido reformular el
     mismo título dos veces, intercambiar palabras sin sentido o usar frases
     que no se entiendan aisladas. Antes de mostrarlas, comprobar: (a) se
     entienden en español natural, (b) tienen verbo y dato concreto, (c) son fieles
     a la publicación, (d) no repiten la misma información y (e) el gancho no es
     clickbait falso.
     Solo ofrecer un bloque único si el post de verdad no necesita contexto extra.
   - **COLORES**: anotar solo palabras informativas con marcado por segmento:
     `REGRESA LA {TEMPORADA|B84DFF}|FFFFFF`. Lo que esté entre `{}` debe ser una
     sola palabra y recibe un único color. Usar hasta cuatro colores de acento
     distintos por propuesta; `FFFFFF` es el color base y no cuenta. Elegir color
     por significado: nombre/evento, novedad, fecha o dato clave. No marcar
     artículos, preposiciones, conjunciones, auxiliares ni pronombres solo para
     llenar la paleta. Nunca colorear frases de varias palabras ni pintar toda la
     línea como decoración. El código valida este marcado y rechaza un acento
     puesto sobre una stopword.
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

El script de render solo confirma `MEDIA:<ruta>` cuando el archivo ha sido creado
y validado; la subida a Telegram la realiza el handler mediante `sendVideo`, con
caption unido y miniatura vertical. No debe imprimir “Enviando” si todavía no ha
hecho una llamada a Telegram.


Cada MP4 debe enviarse mediante el método nativo de Telegram `sendVideo`, con
el título y hashtags en el campo `caption` del mismo mensaje (no como un texto
posterior separado). Adjuntar una miniatura vertical explícita cuando sea
posible; comprobar que el archivo mantenga 1080×1920, SAR 1:1 y DAR 9:16 antes
de enviarlo.

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
automáticamente desde el título (normalmente 1–2 líneas); el renderer puede
envolverlo o recortarlo con `…` para cumplir la safe zone. Si no hay título,
pedir al usuario el texto antes de renderizar.

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
