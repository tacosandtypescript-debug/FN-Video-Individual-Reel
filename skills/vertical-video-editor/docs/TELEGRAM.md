# Montaje en Telegram

## Qué queda resuelto

`scripts/telegram_bot.py` es un adaptador asíncrono basado en
`python-telegram-bot>=22.8,<23`. El flujo es:

```text
/video URL o MP4 adjunto
  -> job_id + carpeta aislada
  -> descarga/probe
  -> ORIGINAL + 3 propuestas
  -> botón inline del propietario
  -> render FFmpeg + validación
  -> miniatura JPEG <=320 px / <200 kB
  -> copia Telegram <= 45 MB
  -> send_video(caption + thumbnail)
```

La aplicación no ejecuta el navegador como fallback. Si `yt-dlp` devuelve
login/private o no puede resolver el enlace, el bot informa `BROWSER_REQUIRED`;
un handler externo debe proporcionar una URL o archivo ya autenticado. Esto
evita que un proceso de navegador quede vivo durante FFmpeg.

La miniatura se genera separada del frame de diagnóstico: Telegram requiere
JPEG, menos de 200 kB y dimensiones máximas de 320 px. El frame original no se
envía directamente como thumbnail.

## Ejecución independiente

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt

export TELEGRAM_BOT_TOKEN='TOKEN_DE_BOTFATHER'
export VVE_JOBS_DIR='/var/lib/fortnite-vve/jobs'
python3 scripts/telegram_bot.py --max-renders 1 --max-jobs 3
```

`--max-renders 1` es el valor recomendado si se comparte una GPU. Las
descargas/análisis pueden continuar mientras un render ocupa el slot. Usa
`--max-renders 2` o `3` solo si la memoria del host lo soporta.
`--max-jobs` limita cuántas preparaciones/renderizados simultáneos acepta el
proceso.

El preset añade la firma `CODIGO: KHETZALGG` como texto ligero centrado abajo.
Su color, opacidad, borde y separación de la zona segura se ajustan en
`references/presets/tiktok_fortnite.json`.

Comandos disponibles:

- `/start`: muestra el uso.
- `/video https://...`: resuelve, descarga y pide aprobación.
- `/video` seguido de un video: descarga el adjunto y pide aprobación.
- `/cancel <job_id>`: marca un trabajo pendiente como cancelado.
- `/cleanup <job_id>`: elimina un trabajo cancelado o fallido y sus archivos.

## Montaje dentro de un bot existente

```python
import sys
sys.path.insert(0, "scripts")          # los módulos viven en scripts/
from telegram_bot import build_application

application = build_application(
    token=BOT_TOKEN,
    jobs_dir="/var/lib/fortnite-vve/jobs",
    max_render_concurrency=1,
    keep_files=False,
)
application.run_polling()
```

`build_application()` registra todos los handlers y guarda el servicio en
`application.bot_data["video_service"]`. Para webhook, conserva la misma
aplicación y usa el método de arranque de webhook de
`python-telegram-bot` en el host; no hay estado dependiente del polling.

## Propuestas editoriales

El `MetadataProposalProvider` incluido no inventa mecánicas: solo usa título,
descripción, autor, plataforma y fecha devueltos por el resolvedor. Por tanto,
es un fallback conservador y no sustituye un analizador de frames o audio.
Para usar un agente editorial del bot, inyecta un objeto con un método `build(job)` que
devuelva un `EditorialProposalSet` con exactamente tres opciones:

```python
application = build_application(
    token=BOT_TOKEN,
    proposal_provider=mi_proveedor_editorial,
)
```

El proveedor debe dejar `status="proposed"`; el callback llama a `choose()` y
solo esa opción llega a `render_video.py`. Cada opción debe tener el mismo
`source_url` y el `job_path` se fija al manifiesto del trabajo antes de
persistirla. Antes de mostrar las opciones, el adaptador aplica el estilo
semántico del preset: texto base blanco, hasta cuatro acentos de la paleta
Fortnite y ningún acento sobre palabras funcionales como `de`, `la`, `en`, `y`,
`o`, `que`, `es`, `un`, `una`, `the`, `of`, `in`, `and`, `is` o `to`. Los
segmentos explícitos se conservan, pero un acento inválido sobre una stopword
se rechaza.

El renderer no acepta desbordes: mide el ancho con la fuente y el borde reales,
envuelve las líneas, reduce el tamaño si falta espacio vertical y usa `…` como
último recurso. Los tamaños solicitados por el proveedor no pueden saltarse la
safe zone.

## Límites y operación

- `VVE_JOBS_DIR` debe estar en almacenamiento local persistente y con espacio
  suficiente para el original, maestro, copia Telegram y frames de chequeo.
- Los adjuntos que el bot descarga desde Telegram están limitados a 20 MB por
  el límite actual del Bot API; las URLs remotas usan el límite independiente
  de entrada configurado abajo.
- La entrada del bot está limitada por defecto a 500 MB; cambia el valor con
  `--max-input-mb`.
- La copia de entrega usa 45 MB para conservar margen frente al límite de
  subida de Telegram. Si el primer encode supera el límite, se re-encodea con
  bitrate calculado y una segunda pasada conservadora.
- Los trabajos enviados se eliminan por defecto después de `send_video`. Usa
  `--keep-files` para conservarlos para auditoría.
- Los trabajos fallidos quedan guardados con su `job_id` para diagnóstico.
- Para restringir el bot a una lista de usuarios, define
  `TELEGRAM_ALLOWED_USER_IDS=12345,67890`.
- Nunca pongas el token en el repositorio; usa una variable de entorno o el
  gestor de secretos del servicio.
