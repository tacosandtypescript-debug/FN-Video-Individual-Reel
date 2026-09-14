# Layout — Geometria relativa

Regla 2-4 del SKILL.

## Canvas

Vertical 9:16. Default 1080x1920. Cualquier resolucion vertical funciona porque
todos los numeros son relativos (`scale_1080` convierte constantes de 1080 a la
resolucion real).

## Video central

- Contain: `scale = min(canvasW/srcW, canvasH/srcH)`; nunca deformar.
- Para fuente horizontal (16:9, 4:3, 1:1) el video ocupa el ancho completo.
- Centrado. Sus limites reales definen el anclaje del texto:
  `videoTop`, `videoBottom`, `videoLeft`, `videoRight`.

## Textos anclados al video

```
topTextBlock.bottom = videoTop - gap
bottomTextBlock.top  = videoBottom + gap
```

- `topGap == bottomGap` siempre.
- Un bloque con N lineas se mide COMPLETO (bbox) antes de posicionarse.
- drawtext `y` no es baseline: empiricamente los glifos ocupan `Y+1..Y+H`,
  `H ~= fs*0.68`. Toda la matematica del bloque usa ese H.
- La jerarquía es independiente por bloque: ARRIBA se trata como titular y
  puede usar una fuente mayor si es corto; ABAJO se ajusta como texto de apoyo.
- El ajuste de safe zone es obligatorio: se mide el ancho real de cada segmento,
  se envuelven las líneas largas y se reduce el tamaño antes de aceptar el
  layout. Una línea imposible se recorta con `…`, nunca se dibuja fuera del
  margen seguro.

## Safe zones (texto, no video)

Si el bloque no cabe (video a sangre completa), se desplaza el bloque ENTERO lo
minimo hasta entrar en la zona segura. Cuando el problema es el ancho o la
altura del copy, el renderer puede envolver/reducir/truncar de manera controlada;
la salida nunca cruza el margen seguro.
