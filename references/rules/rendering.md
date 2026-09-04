# Rendering — reglas de salida

- Motor: FFmpeg (regla 1). Nada de otros editores.
- Decode CUDA (`-hwaccel cuda -hwaccel_output_format cuda`) cuando hay NVIDIA.
  Sin GPU se usa la ruta CPU equivalente.
- El unico paso CPU obligatorio es drawtext (no existe drawtext CUDA en ffmpeg);
  se aplica al frame final ya compuesto.
- Encode con NVENC por defecto: `h264_nvenc -preset p5 -cq N`
  (valores en preset: encode.cq). Si NVENC no está disponible, se usa el
  fallback `libx264` configurado en `encode.cpu_vcodec/cpu_preset`.
- Contenedor: mp4, `+faststart`, audio AAC 96k si existe.
- Verificacion post-render (no opcional): medir gaps reales sobre un frame
  (t=0.3s) con los colores ancla del layout; si difieren >2px del modelo,
  corregir desplazando bloques y re-renderizar (max 3 intentos).
- Antes de renderizar se imprime la geometria completa (debug-layout) para
  detectar errores de posicion al instante.
