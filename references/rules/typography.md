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
  cada propuesta a un máximo de cuatro colores de acento distintos; `FFFFFF` no
  cuenta. El autoestilo evita artículos, preposiciones, conjunciones, auxiliares
  y pronombres (`de`, `la`, `en`, `y`, `o`, `que`, `es`, `un`, `una`, `the`, `of`,
  `in`, `and`, `is`, `to`, `for`).
- La paleta Fortnite es `B84DFF`, `42E8FF`, `FFDD00`, `FF39D7`; se distribuyen
  solo en palabras informativas y no se fuerzan cuando no hay suficientes.
- Todo el copy del overlay se convierte a MAYÚSCULAS y se le quitan tildes y
  diacríticos (`Código` -> `CODIGO`). El texto ORIGINAL de la revisión no cambia.
- El título ARRIBA puede crecer más que el apoyo ABAJO cuando el copy es corto.
  Si el copy es largo, se envuelve, reduce y finalmente se corta con `…` antes de
  cruzar la zona segura.
- Ondulacion suave opcional: `wave` px y `wave_hz` (eje X, animacion sutil).
