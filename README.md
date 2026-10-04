# ElyxiumBot Discord

Bot de Discord para Elyxium Studio con sistemas de embeds, tickets, verificacion y captcha visual.

## Funciones

- Embeds editables y persistentes.
- Sistema de tickets con opciones configurables.
- Sistema de verificacion con captcha.
- Captcha con imagen personalizada, fuente `assets/Minecraft.ttf` y fondo configurable.
- Persistencia MySQL asincrona con copias JSON locales en `data/`.
- Sincronizacion de comandos slash global y por servidor.
- Anuncios de directos y videos para roles Streamer/YouTuber.
- FAQ editable, guardada con el ID `faq`, con preguntas frecuentes de la comunidad.

Para publicar o editar las preguntas frecuentes:

```txt
/embed_enviar canal:#faq embed_id:faq
/editar_embed embed_id:faq
```

El FAQ se crea al arrancar solo si no existe, sin sobrescribir embeds ni ediciones.
Las opciones de tickets usan emojis distintos del servidor para soporte, consulta,
reportes, sugerencias y otras consultas. La actualizacion inicial cambia solo los emojis,
preservando los titulos y descripciones de cada opcion. Reenvia el panel de tickets
para actualizar el selector de un mensaje antiguo:

```txt
/ticket_enviar canal:#tickets config_id:ticket_1
```

Al seleccionar una categoria se abre un formulario privado antes de crear el ticket.
Cada categoria tiene preguntas propias: problema y entorno en soporte; hechos, contexto
y evidencias en reportes; consulta detallada; propuesta y beneficios en sugerencias;
o asunto y solicitud para otras consultas. Las respuestas se incluyen en el embed,
en el transcript y en `active_tickets.json`, replicado a MySQL. Se conservan las
configuraciones existentes y los controles persistentes de tickets ya abiertos.
El formulario vence a los cinco minutos. Se valida autor, servidor, respuestas
obligatorias y ausencia de otro ticket abierto; el bloqueo de creacion evita duplicados.
Los nuevos tickets usan banners por categoria y colores amarillo (soporte), azul claro
(consulta), anaranjado (reportar), morado (sugerencia) y azul (otro).

Los embeds siempre conservan el titulo nativo de Discord para mantener su tamaño.
Los titulos llevan un emoji del servidor antes del texto. Ese emoji no se repite
en la descripcion ni en los campos del mismo embed; no se mueve el titulo a la descripcion.
Al arrancar, una migracion unica cambia los banners guardados de tickets y verificacion
sin tocar textos, campos o botones. Los nuevos banners se guardan en MySQL y JSON.
Despues se pueden seguir editando sin que el siguiente reinicio deshaga esos cambios.
Los mensajes antiguos ya enviados necesitan editarse o reenviarse para actualizarse.

## Anuncios de Creadores

Un administrador selecciona el canal y los dos roles permitidos:

```txt
/creadores configurar canal:#contenido rol_streamer:@Streamer rol_yt:@YouTuber espera_segundos:300
```

Los miembros de cualquiera de esos roles pueden usar `/directo`, `!directo`, `/video`
o `!video` en ese canal. Los administradores pueden invocarlos desde otros canales,
pero el anuncio siempre se publica en el canal configurado.

Se muestra un embed permanente con dos botones: **Directo** y **Video**. Cualquier
miembro con uno de los roles autorizados (o Administrador) puede abrir sus formularios.
El panel se conserva en el canal configurado, se reutiliza sin duplicados y sus botones
se restauran al reiniciar. Si fue eliminado, se vuelve a crear. Solo el formulario abierto
tiene un limite de tres minutos y pertenece a quien lo abrio. El enlace se valida antes de publicar otro
embed, con el emoji de la plataforma, enlace y footer de Elyxium Studio.

El panel y los anuncios usan color morado `#9B59B6` y el banner de creadores.
El formulario permite un titulo y una descripcion opcionales. El anuncio incluye
un boton **Ver directo** o **Ver video** en lugar de un enlace dentro de la descripcion;
el titulo no enlaza al contenido. El avatar y nombre pertenecen al autor de Discord.
No se intenta extraer el avatar del canal externo: las APIs de las plataformas requieren
credenciales o autorizacion del creador, y esas integraciones no estan configuradas.

Se admiten enlaces HTTPS de YouTube, Twitch, Kick y TikTok. Para TikTok usa el enlace
completo `https://www.tiktok.com/@usuario/live` o `.../@usuario/video/ID`, no `vt.tiktok.com`.
Los videos de Twitch usan `/videos/ID` o enlaces de clips; en Kick, enlaces de videos
grabados o de clips. Se rechazan enlaces externos, dominios parecidos, credenciales,
puertos y rutas que no correspondan al contenido. Esta validacion comprueba formato
y plataforma, no que el contenido exista o que el directo este activo; no se abren
los enlaces enviados por los usuarios ni se requiere una API externa.

Los administradores no tienen cooldown en `/directo`, `/video`, `!directo` ni `!video`,
ni entre sus anuncios. Siguen sujetos a validacion de enlaces, permisos del bot,
caducidad del formulario y proteccion contra reenvios del mismo formulario.
Para los demas usuarios hay diez segundos entre paneles por servidor y, por defecto, cinco minutos entre
anuncios por persona, compartidos entre directos y videos. La espera es configurable
entre 60 y 86400 segundos. Los roles se comprueban de nuevo al enviar el formulario.
Configuracion y ultimo anuncio por usuario se guardan en MySQL con recuperacion local
en `data/creators_config.json` y `data/creators_announcements.json`. No se suben a Git.

```txt
/creadores desactivar
```

Para enviar las normas guardadas:

```txt
/embed_enviar canal:#reglas embed_id:reglas
```

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
/sugerencias_admin configurar canal_sugerencias:#sugerencias canal_staff:#revision rol_revision:@Revisor rol_comando:@Colaborador
```

El canal publico tiene un panel permanente con el boton Sugerir, que abre el formulario.
Al enviarlo se publica la sugerencia y una copia para el staff. El bot vuelve a publicar
el panel y elimina su copia anterior para dejarlo al final del canal tras cada nueva
sugerencia. Escribir mensajes normales ya no abre formularios. Estos vencen a los tres
minutos y solo su autor puede enviarlos. El panel y las votaciones sobreviven al reinicio.
Las configuraciones existentes reciben su panel automaticamente al arrancar.

Todos los miembros pueden usar `/sugerencias`, `/sugerencia`, `!sugerencias` o
`!sugerencia`: publican el panel completo con banner y boton Sugerir. En el canal
configurado reemplazan el panel anterior para dejarlo al final, sin duplicados.
En otros canales el panel es temporal y el boton es exclusivo del autor.
El rol `rol_comando` puede usar ambas opciones desde cualquier canal del servidor; las
ideas siempre se publican en el canal de sugerencias, no en el canal donde se invocaron.
Este rol no concede permisos para revisar. Para cambiar el canal y el acceso sin
reconfigurar el staff:

```txt
/sugerencias_admin acceso canal:#sugerencias rol_comando:@Colaborador
```

Omitir rol_comando en acceso desactiva el uso desde otros canales. Los antiguos
subcomandos `/sugerencias ...` ahora estan en `/sugerencias_admin ...`.
El panel usa el banner de sugerencias. Todos los embeds nuevos o actualizados llevan
el logo del bot y el footer `© Elyxium Studio Copyright 2026` desde `common.StudioEmbed`.

Cada persona tiene un voto: repetir la opcion lo retira y cambiarla reemplaza el voto.
Hay cinco segundos entre cambios de voto y tres minutos entre sugerencias.
El estado pendiente es amarillo; aceptado, verde; denegado, rojo. Revisar cierra la votacion.
El rol configurado y los miembros con permiso Administrador pueden aceptar, denegar
o eliminar. Los administradores tambien pueden usar los comandos de sugerencias desde
cualquier canal, sin el rol de acceso. Denegar y eliminar requieren un motivo. Eliminar borra ambas publicaciones
y conserva un registro de auditoria. Los estados, votos y configuracion se guardan en
MySQL y JSON; los botones de publicaciones se restauran tras reiniciar.

Si falla el envio o se borran mensajes, el rol de revision puede reconstruirlos:

```txt
/sugerencias_admin sincronizar sugerencia_id:ID
/sugerencias_admin panel
/sugerencias_admin desactivar
```

Limites: 500 formularios simultaneos, 10000 registros y 20000 votantes por
sugerencia. Opera una sola instancia del bot. El rol de revision necesita ver el canal
privado y su historial; el bot necesita ver ambos canales, enviar mensajes, insertar
enlaces y leer historial. El panel se mueve cuando se publica una sugerencia, no con
cada mensaje de conversacion ni cada voto. Si falla el envio, se conserva el panel
anterior; si falla eliminarlo, se guarda su ID para reintentar y queda inactivo.

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
