# Safe zones TikTok / Reels

Zonas a proteger (informacion del UI): botones de la derecha, nombre de usuario,
caption, controles inferiores.

- Fracciones por defecto del preset:
  - izquierda: 0.056 x canvasW
  - derecha:   0.056 x canvasW
  - arriba:    0.0725 x canvasH
  - abajo:     0.174 x canvasH desde abajo
- Regla principal: los textos estan PEGADOS al video (gap pequeno).
  Las safe zones solo desplazan el bloque lo minimo cuando no cabe.
- El video central puede ocupar el ancho completo aunque eso entre en las
  columnas laterales de UI: la restriccion es para TEXTO e info critica.
