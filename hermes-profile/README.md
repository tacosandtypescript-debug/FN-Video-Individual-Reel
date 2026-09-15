# Respaldo del perfil Hermes `fn-bot`

`fn-bot-profile.tar.gz` es un snapshot generado con `hermes profile export` después de sincronizar la skill `vertical-video-editor` y guardar el repositorio en:

```text
workspace/FN-Video-Individual-Reel/
```

El exportador excluye `.env` y `auth.json`, y sanea valores con forma de secreto en archivos de texto. El snapshot conserva el estado no credential de Hermes, incluidas sesiones, logs, cachés y la base de datos del perfil, porque forma parte del respaldo completo solicitado.

Para restaurarlo en una instalación de Hermes:

```bash
hermes profile import fn-bot-profile.tar.gz --name fn-bot
```
