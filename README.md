# ElyxiumBot Discord

Bot de Discord para Elyxium Studio con sistemas de embeds, tickets, verificacion y captcha visual.

## Funciones

- Embeds editables y persistentes.
- Sistema de tickets con opciones configurables.
- Sistema de verificacion con captcha.
- Captcha con imagen personalizada, fuente `assets/Minecraft.ttf` y fondo configurable.
- Persistencia MySQL asincrona con copias JSON locales en `data/`.
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
MYSQL_HOST=db-us.supercores.host
MYSQL_PORT=3306
MYSQL_DATABASE=s3510_config-bot
MYSQL_USER=u3510_LXJHlxKhPd
MYSQL_PASSWORD=tu_password
```

`ADMIN_ROLE_ID` puede quedar en `0` si solo quieres usar permisos de administrador de Discord.

## Pterodactyl

Startup recomendado:

```bash
if [[ -d .git ]] && [[ "${AUTO_UPDATE}" == "1" ]]; then git pull --ff-only; fi; pip install --prefix .local -r /home/container/requirements.txt && /usr/local/bin/python /home/container/main.py
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

`storage.py` crea la tabla `bot_documents` automaticamente. En el primer inicio,
importa los JSON existentes sin reemplazar documentos ya almacenados en MySQL.
En siguientes inicios MySQL restaura las copias locales. Los cambios se escriben
en JSON y se sincronizan en segundo plano; si MySQL falla durante una escritura,
se reintenta. Con MySQL configurado, un fallo al conectar durante el arranque
impide iniciar el bot para evitar usar datos antiguos. Sin MYSQL_HOST se usa JSON.
El usuario MySQL necesita SELECT, INSERT, UPDATE y CREATE en esta base.
Ejecuta una sola instancia del bot por base de datos: este almacenamiento de
documentos y los bloqueos de tickets no coordinan varias instancias.

El captcha admite cinco intentos por codigo, vence a los 180 segundos y esta
vinculado al usuario, servidor y rol. El boton no vuelve a enviar un codigo activo.
Las imagenes remotas solo admiten HTTPS de Cloudinary o CDN de Discord, sin
redirecciones y con limite de 8 MiB. Los transcripts contienen hasta 5000 mensajes.

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

## Sugerencias

Configura dos canales diferentes (el del staff debe ser privado) y un rol de revision:

```txt
/sugerencias configurar canal_sugerencias:#sugerencias canal_staff:#revision rol_revision:@Revisor
```

Al escribir en el canal publico aparece un boton temporal de tres minutos, exclusivo
del autor. El boton abre el formulario; Discord no permite abrir modales directamente
desde un mensaje normal. Al enviarlo se publica la sugerencia y una copia para el staff.
El mensaje original y el aviso se eliminan si el bot tiene Gestionar mensajes y la
sugerencia se publico. Si se cancela o vence el formulario, el original se conserva.

Cada persona tiene un voto: repetir la opcion lo retira y cambiarla reemplaza el voto.
Hay cinco segundos entre cambios de voto y tres minutos entre sugerencias.
El estado pendiente es amarillo; aceptado, verde; denegado, rojo. Revisar cierra la votacion.
Solo el rol configurado puede aceptar, denegar o eliminar, incluso si otro usuario es
administrador. Denegar y eliminar requieren un motivo. Eliminar borra ambas publicaciones
y conserva un registro de auditoria. Los estados, votos y configuracion se guardan en
MySQL y JSON; los botones de publicaciones se restauran tras reiniciar.

Si falla el envio o se borran mensajes, el rol de revision puede reconstruirlos:

```txt
/sugerencias sincronizar sugerencia_id:ID
/sugerencias desactivar
```

Limites: 500 formularios temporales simultaneos, 10000 registros y 20000 votantes por
sugerencia. Opera una sola instancia del bot. El rol de revision necesita ver el canal
privado y su historial; el bot necesita ver ambos canales, enviar mensajes, insertar
enlaces y leer historial. Gestionar mensajes permite limpiar mensajes de los usuarios.

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
/verificacion_reparar
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
