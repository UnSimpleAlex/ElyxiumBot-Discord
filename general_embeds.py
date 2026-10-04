from typing import Optional

import discord
from discord import app_commands

from common import admin_app_check, parse_hex_color, read_json, write_json, ResponsiveView, StudioEmbed, SERVER_EMOJIS, BRAND_FOOTER, BRAND_LOGO


EMBEDS_STORAGE_FILE = "data/embeds_storage.json"

embeds_storage = {}


class EmbedBuilder:
    def __init__(self):
        self.title = None
        self.description = None
        self.color = None
        self.image_url = None
        self.thumbnail_url = None
        self.footer_text = None
        self.footer_icon = None
        self.author_name = None
        self.author_icon = None
        self.fields = []
        self.timestamp = False

    @classmethod
    def from_dict(cls, data):
        builder = cls()
        builder.title = data.get("title")
        builder.description = data.get("description")
        builder.color = data.get("color")
        builder.image_url = data.get("image_url")
        builder.thumbnail_url = data.get("thumbnail_url")
        builder.footer_text = data.get("footer_text")
        builder.footer_icon = data.get("footer_icon")
        builder.author_name = data.get("author_name")
        builder.author_icon = data.get("author_icon")
        builder.fields = data.get("fields", [])
        builder.timestamp = data.get("timestamp", False)
        return builder

    def to_json(self):
        return {
            "title": self.title,
            "description": self.description,
            "color": self.color,
            "image_url": self.image_url,
            "thumbnail_url": self.thumbnail_url,
            "footer_text": self.footer_text,
            "footer_icon": self.footer_icon,
            "author_name": self.author_name,
            "author_icon": self.author_icon,
            "fields": self.fields,
            "timestamp": self.timestamp,
        }

    def to_embed(self):
        embed = StudioEmbed()

        if self.title:
            embed.title = self.title
        if self.description:
            embed.description = self.description
        embed.color = parse_hex_color(self.color)

        if self.image_url:
            embed.set_image(url=self.image_url)
        if self.thumbnail_url:
            embed.set_thumbnail(url=self.thumbnail_url)
        if self.footer_text:
            embed.set_footer(text=self.footer_text, icon_url=self.footer_icon)
        if self.author_name:
            embed.set_author(name=self.author_name, icon_url=self.author_icon)

        for field in self.fields:
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field.get("inline", False),
            )

        if self.timestamp:
            embed.timestamp = discord.utils.utcnow()

        return embed

    def summary(self):
        info = {}
        if self.title:
            info["Título"] = self.title
        if self.description:
            info["Descripción"] = self.description[:100] + "..." if len(self.description) > 100 else self.description
        if self.color:
            info["Color"] = self.color
        if self.image_url:
            info["Imagen"] = self.image_url
        if self.thumbnail_url:
            info["Miniatura"] = self.thumbnail_url
        if self.footer_text:
            info["Footer"] = self.footer_text
        if self.author_name:
            info["Autor"] = self.author_name
        if self.fields:
            info["Campos"] = f"{len(self.fields)} campos"
        if self.timestamp:
            info["Timestamp"] = "Activado"
        return info


def build_faq():
    builder = EmbedBuilder()
    builder.title = f"{SERVER_EMOJIS['badge']} 𝙿𝚁𝙴𝙶𝚄𝙽𝚃𝙰𝚂 𝙵𝚁𝙴𝙲𝚄𝙴𝙽𝚃𝙴𝚂"
    builder.description = f"{SERVER_EMOJIS['community']} **RESUELVE TUS DUDAS SOBRE ELYXIUM STUDIO**\n\nEncuentra aquí las respuestas a las consultas más habituales de nuestra comunidad."
    builder.color = '#26B99A'
    builder.thumbnail_url = BRAND_LOGO
    builder.footer_text, builder.footer_icon = BRAND_FOOTER, BRAND_LOGO
    questions = (
        ('shield', '¿CÓMO ACCEDO A LOS CANALES?', 'Completa la **VERIFICACIÓN** del servidor. Presiona **VERIFICAR**, revisa el código de la imagen y usa **INGRESAR CÓDIGO** para recibir tu rol.'),
        ('key', '¿QUÉ HAGO SI NO RECIBO EL CÓDIGO?', 'Revisa tus mensajes privados y permite mensajes del servidor. Si el código venció, solicita uno nuevo. **NO COMPARTAS TU CÓDIGO** con otras personas.'),
        ('wrench', '¿CÓMO CONTACTO AL EQUIPO DE SOPORTE?', 'Abre un **TICKET** y elige la categoría que corresponda. Explica tu consulta con detalles y adjunta capturas si ayudan. No compartas contraseñas ni datos sensibles.'),
        ('document', '¿DÓNDE PUEDO CONSULTAR LAS NORMAS?', 'Lee el embed de **NORMAS** publicado en el servidor antes de participar. Se aplica a los canales de texto, voz, tickets y actividades de la comunidad.'),
        ('pencil', '¿CÓMO ENVÍO UNA SUGERENCIA?', 'Usa el botón **SUGERIR** del panel de sugerencias. La comunidad podrá votar tu propuesta y el staff la revisará. Los votos no garantizan su aceptación.'),
        ('youtube', '¿PUEDO COMPARTIR MIS DIRECTOS Y VIDEOS?', 'Los roles **STREAMER** o **YOUTUBER** autorizados pueden usar el panel de creadores en el canal configurado. Se admiten enlaces de **YOUTUBE, TWITCH, KICK Y TIKTOK**.'),
        ('warning', '¿QUÉ HAGO SI UN BOTÓN NO FUNCIONA?', 'Vuelve a intentarlo desde el panel más reciente. Si el problema continúa, avisa al staff con una captura y el nombre del botón. **NUNCA ENVÍES TU CONTRASEÑA O TOKEN**.'),
    )
    builder.fields = [{'name': f'{SERVER_EMOJIS[key]} {question}', 'value': answer + '\n\u200b', 'inline': False}
                      for key, question, answer in questions]
    return builder


def ensure_faq():
    documents = read_json(EMBEDS_STORAGE_FILE, {})
    if 'faq' not in documents:
        documents['faq'] = build_faq().to_json()
        write_json(EMBEDS_STORAGE_FILE, documents)


def count_embeds():
    return len(embeds_storage)


def save_embeds_storage():
    try:
        write_json(
            EMBEDS_STORAGE_FILE,
            {embed_id: builder.to_json() for embed_id, builder in embeds_storage.items()},
        )
        print(f"✅ Embeds guardados en {EMBEDS_STORAGE_FILE}")
    except Exception as exc:
        print(f"❌ Error guardando embeds: {exc}")


def load_embeds_storage():
    global embeds_storage
    try:
        embeds_data = read_json(EMBEDS_STORAGE_FILE, {})
        embeds_storage = {
            embed_id: EmbedBuilder.from_dict(data)
            for embed_id, data in embeds_data.items()
            if isinstance(data, dict)
        }
        print(f"✅ {len(embeds_storage)} embeds cargados desde {EMBEDS_STORAGE_FILE}")
    except Exception as exc:
        print(f"❌ Error cargando embeds: {exc}")
        embeds_storage = {}


EMBED_EDIT_OPTIONS = {
    "title": ("Título", "Título del embed", discord.TextStyle.short, 256),
    "description": ("Descripción", "Descripción del embed", discord.TextStyle.paragraph, 4000),
    "color": ("Color", "Color hexadecimal, ejemplo: #8A001E", discord.TextStyle.short, 7),
    "image_url": ("Imagen", "URL de la imagen principal", discord.TextStyle.short, 1000),
    "thumbnail_url": ("Miniatura", "URL de la miniatura", discord.TextStyle.short, 1000),
    "footer_text": ("Footer", "Texto del footer", discord.TextStyle.short, 2048),
    "footer_icon": ("Icono footer", "URL del icono del footer", discord.TextStyle.short, 1000),
    "author_name": ("Autor", "Nombre del autor", discord.TextStyle.short, 256),
    "author_icon": ("Icono autor", "URL del icono del autor", discord.TextStyle.short, 1000),
}


class EditEmbedView(ResponsiveView):
    def __init__(self, embed_id, embed_builder, user_id):
        super().__init__(timeout=300)
        self.embed_id = embed_id
        self.embed_builder = embed_builder
        self.user_id = user_id
        self.add_item(EditEmbedFieldSelect(embed_id, embed_builder, user_id))

    async def _guard_user(self, interaction):
        if interaction.user.id == self.user_id:
            return True

        await interaction.response.send_message("❌ Solo quien abrió el editor puede usarlo.", ephemeral=True)
        return False

    @discord.ui.button(label="⏰ Activar/Desactivar Timestamp", style=discord.ButtonStyle.secondary)
    async def toggle_timestamp(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return

        self.embed_builder.timestamp = not self.embed_builder.timestamp
        embeds_storage[self.embed_id] = self.embed_builder
        save_embeds_storage()
        await interaction.response.edit_message(
            content=f"✅ **Timestamp {'activado' if self.embed_builder.timestamp else 'desactivado'}**\n**Preview del embed `{self.embed_id}`:**",
            embed=self.embed_builder.to_embed(),
            view=EditEmbedView(self.embed_id, self.embed_builder, interaction.user.id),
        )

    @discord.ui.button(label="➕ Agregar Campo", style=discord.ButtonStyle.secondary)
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return

        modal = AddEmbedFieldModal()
        modal.embed_builder = self.embed_builder
        modal.embed_id = self.embed_id
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🧹 Limpiar Campos", style=discord.ButtonStyle.danger)
    async def clear_fields(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._guard_user(interaction):
            return

        self.embed_builder.fields = []
        embeds_storage[self.embed_id] = self.embed_builder
        save_embeds_storage()
        await interaction.response.edit_message(
            content=f"✅ **Campos eliminados**\n**Preview del embed `{self.embed_id}`:**",
            embed=self.embed_builder.to_embed(),
            view=EditEmbedView(self.embed_id, self.embed_builder, interaction.user.id),
        )


class EditEmbedFieldSelect(discord.ui.Select):
    def __init__(self, embed_id, embed_builder, user_id):
        self.embed_id = embed_id
        self.embed_builder = embed_builder
        self.user_id = user_id
        options = [
            discord.SelectOption(label=label, description=description, value=field_type)
            for field_type, (label, description, _style, _max_length) in EMBED_EDIT_OPTIONS.items()
        ]
        super().__init__(
            placeholder="Elige qué parte del embed quieres editar...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Solo quien abrió el editor puede usarlo.", ephemeral=True)
            return

        field_type = self.values[0]
        label, placeholder, style, max_length = EMBED_EDIT_OPTIONS[field_type]
        modal = EditModal(
            label,
            getattr(self.embed_builder, field_type) or "",
            field_type,
            placeholder,
            style,
            max_length,
        )
        modal.embed_builder = self.embed_builder
        modal.embed_id = self.embed_id
        await interaction.response.send_modal(modal)


class EditModal(discord.ui.Modal):
    def __init__(self, field_name, current_value, field_type, placeholder=None, style=None, max_length=None):
        super().__init__(title=f"Editar {field_name}")
        self.field_type = field_type
        self.text_input = discord.ui.TextInput(
            label=field_name,
            default=current_value,
            placeholder=placeholder,
            max_length=max_length or (4000 if field_type == "description" else 256),
            required=False,
            style=style or (discord.TextStyle.paragraph if field_type == "description" else discord.TextStyle.short),
        )
        self.add_item(self.text_input)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.text_input.value.strip()
        setattr(self.embed_builder, self.field_type, value or None)
        embeds_storage[self.embed_id] = self.embed_builder
        save_embeds_storage()

        await interaction.response.edit_message(
            content=f"✅ **{self.text_input.label} actualizado**\n**Preview del embed `{self.embed_id}`:**",
            embed=self.embed_builder.to_embed(),
            view=EditEmbedView(self.embed_id, self.embed_builder, interaction.user.id),
        )


class AddEmbedFieldModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Agregar Campo")
        self.field_name = discord.ui.TextInput(label="Nombre", max_length=256, required=True)
        self.field_value = discord.ui.TextInput(
            label="Valor",
            max_length=1024,
            required=True,
            style=discord.TextStyle.paragraph,
        )
        self.inline = discord.ui.TextInput(label="Inline (si/no)", default="no", max_length=2, required=False)
        self.add_item(self.field_name)
        self.add_item(self.field_value)
        self.add_item(self.inline)

    async def on_submit(self, interaction: discord.Interaction):
        self.embed_builder.fields.append(
            {
                "name": self.field_name.value,
                "value": self.field_value.value,
                "inline": self.inline.value.lower() in ["si", "sí", "s", "yes", "y"],
            }
        )
        embeds_storage[self.embed_id] = self.embed_builder
        save_embeds_storage()
        await interaction.response.edit_message(
            content=f"✅ **Campo agregado**\n**Preview del embed `{self.embed_id}`:**",
            embed=self.embed_builder.to_embed(),
            view=EditEmbedView(self.embed_id, self.embed_builder, interaction.user.id),
        )


def setup(bot, admin_role_id):
    ensure_faq()
    load_embeds_storage()
    admin_only = admin_app_check(admin_role_id)

    @bot.tree.command(name="config_embed", description="Crea un embed personalizado")
    @admin_only
    @app_commands.describe(
        embed_id="ID para guardar el embed, ejemplo: reglas",
        titulo="Título del embed",
        descripcion="Descripción del embed",
        color="Color hexadecimal, ejemplo: #8A001E",
        imagen="URL de imagen principal",
        miniatura="URL de miniatura",
        footer="Texto del footer",
        autor="Nombre del autor",
        timestamp="Agregar fecha/hora al embed",
    )
    async def config_embed(
        interaction: discord.Interaction,
        embed_id: str,
        titulo: Optional[str] = None,
        descripcion: Optional[str] = None,
        color: Optional[str] = "#8A001E",
        imagen: Optional[str] = None,
        miniatura: Optional[str] = None,
        footer: Optional[str] = None,
        autor: Optional[str] = None,
        timestamp: bool = False,
    ):
        builder = EmbedBuilder()
        builder.title = titulo
        builder.description = descripcion
        builder.color = color
        builder.image_url = imagen
        builder.thumbnail_url = miniatura
        builder.footer_text = footer
        builder.author_name = autor
        builder.timestamp = timestamp

        embeds_storage[embed_id] = builder
        save_embeds_storage()

        await interaction.response.send_message(
            content=f"✅ **Embed `{embed_id}` creado/actualizado.** Usa el menú para editar cualquier parte:",
            embed=builder.to_embed(),
            view=EditEmbedView(embed_id, builder, interaction.user.id),
            ephemeral=True,
        )

    @bot.tree.command(name="editar_embed", description="Edita un embed guardado")
    @admin_only
    @app_commands.describe(embed_id="ID del embed guardado")
    async def editar_embed(interaction: discord.Interaction, embed_id: str):
        if embed_id not in embeds_storage:
            await interaction.response.send_message(f"❌ No existe el embed `{embed_id}`.", ephemeral=True)
            return

        builder = embeds_storage[embed_id]
        await interaction.response.send_message(
            content=f"🛠️ **Editando embed `{embed_id}`:**",
            embed=builder.to_embed(),
            view=EditEmbedView(embed_id, builder, interaction.user.id),
            ephemeral=True,
        )

    @bot.tree.command(name="embed_enviar", description="Envía un embed guardado a un canal")
    @admin_only
    @app_commands.describe(canal="Canal donde se enviará el embed", embed_id="ID del embed guardado")
    async def embed_enviar(interaction: discord.Interaction, canal: discord.TextChannel, embed_id: str):
        if embed_id not in embeds_storage:
            await interaction.response.send_message(f"❌ No existe el embed `{embed_id}`.", ephemeral=True)
            return

        await canal.send(embed=embeds_storage[embed_id].to_embed())
        await interaction.response.send_message(f"✅ Embed `{embed_id}` enviado en {canal.mention}.", ephemeral=True)

    @bot.tree.command(name="embed_dm", description="Envía un embed guardado por mensaje directo a un usuario")
    @admin_only
    @app_commands.describe(usuario="Usuario que recibirá el mensaje directo", embed_id="ID del embed guardado")
    async def embed_dm(interaction: discord.Interaction, usuario: discord.User, embed_id: str):
        if embed_id not in embeds_storage:
            await interaction.response.send_message(f"❌ No existe el embed `{embed_id}`.", ephemeral=True)
            return

        try:
            await usuario.send(embed=embeds_storage[embed_id].to_embed())
            await interaction.response.send_message(
                f"✅ Embed `{embed_id}` enviado por MD a {usuario.mention}.",
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ No pude enviar el MD. El usuario puede tener los mensajes directos cerrados o bloqueado al bot.",
                ephemeral=True,
            )
        except Exception as exc:
            await interaction.response.send_message(f"❌ Error enviando el MD: {exc}", ephemeral=True)

    @bot.tree.command(name="listar_embeds", description="Lista todos los embeds guardados")
    @admin_only
    async def listar_embeds(interaction: discord.Interaction):
        if not embeds_storage:
            await interaction.response.send_message("📝 No hay embeds guardados.", ephemeral=True)
            return

        embed = StudioEmbed(title="📋 Embeds Guardados", color=discord.Color.blue())
        for embed_id, builder in embeds_storage.items():
            info = builder.summary()
            summary = "\n".join([f"**{key}:** {value}" for key, value in info.items()]) or "*Sin contenido configurado*"
            embed.add_field(name=embed_id, value=summary[:1024], inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="eliminar_embed", description="Elimina un embed guardado")
    @admin_only
    @app_commands.describe(embed_id="ID del embed guardado")
    async def eliminar_embed(interaction: discord.Interaction, embed_id: str):
        if embed_id not in embeds_storage:
            await interaction.response.send_message(f"❌ No existe el embed `{embed_id}`.", ephemeral=True)
            return

        del embeds_storage[embed_id]
        save_embeds_storage()
        await interaction.response.send_message(f"✅ Embed `{embed_id}` eliminado.", ephemeral=True)

    @config_embed.error
    @editar_embed.error
    @embed_enviar.error
    @embed_dm.error
    @listar_embeds.error
    @eliminar_embed.error
    async def embed_commands_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            message = "❌ No tienes permisos para usar este comando."
        else:
            message = f"❌ Error: {error}"

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
