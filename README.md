# ElyxiumBot Discord

Bot de Discord para Elyxium Studio con sistemas de embeds, tickets, verificacion y captcha visual.

## Funciones

- Embeds editables y persistentes.
- Sistema de tickets con opciones configurables.
- Sistema de verificacion con captcha.
- Captcha con imagen personalizada, fuente `assets/Minecraft.ttf` y fondo configurable.
- Persistencia en archivos JSON dentro de `data/`.
- Sincronizacion de comandos slash global y por servidor.

## Requisitos

- Python 3.13 recomendado en Pterodactyl.
- Token de bot de Discord.
- Dependencias en `requirements.txt`.

Instalacion local:

```bash
pip install -r requirements.txt
```

## Configuracion

Crea un archivo `.env` en el servidor, no lo subas a GitHub:

```env
DISCORD_TOKEN=tu_token_del_bot
ADMIN_ROLE_ID=0
SUPPORT_ROLE_ID=0
TICKET_CATEGORY_ID=0
TRANSCRIPT_CHANNEL_ID=0
```

`ADMIN_ROLE_ID` puede quedar en `0` si solo quieres usar permisos de administrador de Discord.

## Pterodactyl

Startup recomendado:

```bash
if [[ -d .git ]] && [[ "${AUTO_UPDATE}" == "1" ]]; then git pull; fi; pip install -U --prefix .local "discord.py>=2.3.0" "python-dotenv>=1.0.0" "Pillow>=10.0.0"; /usr/local/bin/python /home/container/main.py
```

Variables recomendadas:

```txt
GIT_ADDRESS=https://github.com/UnSimpleAlex/ElyxiumBot-Discord.git
BRANCH=main
USER_UPLOAD=0
AUTO_UPDATE=1
REQUIREMENTS_FILE=requirements.txt
PY_FILE=main.py
```

Si el servidor ya fue subido manualmente y no tiene `.git`, usa reinstall/clone desde Pterodactyl o clona el repo manualmente. Antes de reinstalar, guarda copia de `.env`, `data/` y `assets/` si contienen cambios privados.

## Archivos importantes

- `main.py`: arranque del bot y carga de sistemas.
- `general_embeds.py`: comandos generales de embeds.
- `ticket.py`: sistema de tickets.
- `verificacion.py`: sistema de verificacion.
- `captcha.py`: codigos captcha, imagen generada y modal de ingreso.
- `common.py`: utilidades compartidas de JSON, consola y permisos.
- `assets/captcha_background.png`: fondo fallback del captcha.
- `assets/Minecraft.ttf`: fuente del codigo captcha.
- `data/*.json`: configuraciones guardadas.

## Datos ignorados

No se versionan:

- `.env`
- `.local/`
- `.cache/`
- `__pycache__/`
- `data/captcha_codes.json`
- `data/active_tickets.json`
- `assets/captcha_preview.png`

Esos archivos son secretos, dependencias instaladas, cache o estado temporal.

## Comandos principales

Embeds:

```txt
/config_embed
/editar_embed
/embed_enviar
/embed_dm
/listar_embeds
/eliminar_embed
```

Tickets:

```txt
/ticket_config
/ticket_enviar
/ticket_stats
/ticket edit_embed
/ticket options
/ticket edit_options
/ticket set_emoji
/ticket set_option_text
```

Verificacion y captcha:

```txt
/verificacion_setup
/verificacion_enviar
/verificacion_lista
/verificacion edit_embed
/captcha_image_config
/captcha_image_preview
/captcha_embed_config
/captcha_embed_preview
/captcha_prompt_config
/captcha_prompt_preview
/captcha_generar
/captcha_info
```
