# Rendering — reglas de salida

- Motor: FFmpeg (regla 1). Nada de otros editores.
- Decode y encode CUDA/NVENC (`-hwaccel cuda -hwaccel_output_format cuda`,
  `h264_nvenc`) cuando hay NVIDIA. Sin GPU se usa la ruta CPU equivalente.
- Los filtros se mantienen en CPU cuando no hay un equivalente CUDA fiable:
  `gblur`, `geq`, `alphamerge`, `overlay` y `drawtext`. En esta máquina,
  forzar OpenCL/Vulkan añade transferencias y es más lento que el camino CPU.
- El preset fija `output_fps: 60`; el grafo aplica `fps=60` antes del formato final.
- El modo `cover_mode: precrop` recorta al aspecto 9:16 antes de escalar al
  canvas, evitando crear un intermedio 3414x1920 sin deformar el centro.
- Encode con NVENC por defecto: `h264_nvenc -preset p5 -cq N`
  (valores en preset: encode.cq). Si NVENC no está disponible, se usa el
  fallback `libx264` configurado en `encode.cpu_vcodec/cpu_preset`.
- Contenedor: mp4, `+faststart`, audio AAC 96k si existe.
- Verificacion post-render (no opcional): medir gaps reales sobre un frame
  (t=0.3s) con los colores ancla del layout; si difieren >2px del modelo,
  corregir desplazando bloques y re-renderizar (max 3 intentos).
- Antes de renderizar se imprime la geometria completa (debug-layout) para
  detectar errores de posicion al instante.
