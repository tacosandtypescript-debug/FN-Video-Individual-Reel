# Tipografia

Valores por defecto viven en el preset (`references/presets/*.json`), no en codigo.

- Fuente del preset (ej. `Barlow-ExtraBoldItalic.ttf`).
- Tamano base proporcional: `font_size_1080` (60 -> 60px en canvas de 1080 de alto).
- `spacing_1080` separa lineas dentro de un bloque.
- `outline` = borde negro de drawtext.
- Color base por linea en el bloque: `TEXTO|HEXCOLOR`. Blanco (`FFFFFF`) para texto
  normal; los acentos se marcan por palabra, por ejemplo:
  `SUBE {5|B84DFF} NIVELES|FFFFFF`.
- Cada segmento `{PALABRA|RRGGBB}` debe contener exactamente una palabra. Limitar
  cada propuesta a un máximo de tres colores de acento distintos; `FFFFFF` no cuenta.
- Ondulacion suave opcional: `wave` px y `wave_hz` (eje X, animacion sutil).
