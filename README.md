# Fortnite Vertical Video Editor

Skill de edición vertical 9:16 para videos de Fortnite y noticias de X/Twitter.

## Estructura del proyecto

```text
SKILL.md                  Contrato completo: reglas, flujo editorial y pipeline
README.md                 Esta guía: instalación, uso y estructura
CHANGELOG.md              Historial de cambios
LICENSE                   MIT
requirements.txt          Dependencias Python (y de sistema, comentadas)
docs/
  COMMANDS.md             Órdenes completas de instalación y operación
  TELEGRAM.md             Guía de montaje del bot de Telegram
scripts/                  Motor de edición (resolver, geometría, render, bot y doctor)
references/
  presets/                Parámetros visuales (`tiktok_fortnite.json`)
  rules/                  Reglas de fondo, layout, render, safe zones, tipografía
tests/                    Batería de pruebas automatizadas
```

El motor se ejecuta con `scripts/` en el `PYTHONPATH`; los scripts se importan
entre sí por nombre de módulo (por ejemplo `import calculate_layout`).

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

Requiere Python 3.11+, FFmpeg/FFprobe, `yt-dlp`, Pillow y NumPy. Las dependencias
Python, incluido `yt-dlp`, están declaradas con límites de versión en
`requirements.txt`. La GPU NVIDIA es opcional, pero si está disponible el render
usa `h264_nvenc`; de lo contrario usa el fallback CPU configurado en el preset.

Después de instalar las dependencias, valida el entorno con:

```bash
python3 scripts/check_installation.py
```

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
cd tests
python3 -m unittest discover -p 'test_*.py' -v
```

## Bot de Telegram

La integración lista para montar está en `scripts/telegram_bot.py`. Usa
`python-telegram-bot` 22.x, crea una carpeta aislada por `job_id`, muestra tres
propuestas con botones inline y solo renderiza la opción aprobada. También
acepta `/video <URL>` y `/video` seguido de un MP4 adjunto.

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN='123456:token-de-BotFather'
python3 scripts/telegram_bot.py --jobs-dir /var/lib/fortnite-vve/jobs --max-renders 1
```

La guía de integración con un bot existente está en
`docs/TELEGRAM.md`. El proveedor incluido es conservador y usa únicamente
metadata de la fuente; no afirma mecánicas que no hayan sido confirmadas por un
analizador externo. Para copy editorial basado en el contenido del video se
puede inyectar un `ProposalProvider` propio sin modificar el motor FFmpeg.

## Documentación completa

Consulta `SKILL.md` y `references/rules/` para el flujo editorial, geometría,
zona segura, fondo, tipografía, render y validación. Las órdenes completas de
instalación y operación están en `docs/COMMANDS.md`.

| Documento | Contenido |
| --- | --- |
| `SKILL.md` | Reglas obligatorias, flujo editorial y pipeline completo |
| `docs/COMMANDS.md` | Órdenes de instalación, render, validación y trabajos simultáneos |
| `docs/TELEGRAM.md` | Montaje del bot, comandos y webhook |
| `references/rules/` | Detalle de fondo, layout, render, safe zones y tipografía |
| `CHANGELOG.md` | Historial de cambios del proyecto |

## Licencia y origen

Proyecto privado de uso personal para el flujo de contenido de Isaac. Licencia
MIT, véase `LICENSE`.
