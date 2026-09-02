# Background — cover, prohibido stretch

Regla 5 del SKILL.

## Correcto (unico permitido)

```
[bg]scale=WxH:force_original_aspect_ratio=increase,
    crop=WxH:(iw-W)/2:(ih-H)/2,
    gblur=sigma=BLUR
```

1. Escala conservando AR hasta cubrir todo el canvas (increase).
2. Recorta el sobrante, centrado.
3. Blur moderado (`gblur`, sigma del preset) A LA RESOLUCION FINAL.

## Prohibido

- `scale=1080:1920` puro (o equivalente) que deforme el AR.
- downscale extremo (p.ej. 270x480) -> blur -> upscale (destruye calidad).
- blur excesivo que convierta el fondo en mancha irreconocible.

## Log util

```
Background source: 1280x720
Background scaled: 3414x1920 (cover, AR intacto)
Background crop: 1080x1920 centrado
Background aspect ratio preserved: true
```

`cover_dims()` en `scripts/build_background.py` calcula las dimensiones del log.
