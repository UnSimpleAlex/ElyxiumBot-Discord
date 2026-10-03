import discord
from discord.ext import commands
from discord import app_commands
import os
from typing import Optional
import asyncio
import logging

from common import configure_console, read_json, write_json, ResponsiveView


configure_console()

# Archivo de persistencia
VERIFICATION_ROLES_FILE = "data/verification_roles.json"
VERIFICATION_EMBEDS_FILE = "data/verification_embeds.json"
VERIFICATION_BUTTONS_FILE = "data/verification_buttons.json"
LEGACY_EMBEDS_STORAGE_FILE = "data/embeds_storage.json"

# Variables globales
verification_roles = {}
verification_embeds = {}
verification_buttons = {}

def save_verification_roles():
    """Guarda los roles de verificación en archivo JSON"""
    try:
        write_json(VERIFICATION_ROLES_FILE, verification_roles)
        print(f"✅ Roles de verificación guardados")
    except Exception as e:
        print(f"❌ Error guardando roles de verificación: {e}")

def load_verification_roles():
    """Carga los roles de verificación desde archivo JSON"""
    global verification_roles
    try:
        if os.path.exists(VERIFICATION_ROLES_FILE):
            verification_roles = read_json(VERIFICATION_ROLES_FILE, {})
            verification_roles = normalize_verification_roles(verification_roles)
            print(f"✅ {len(verification_roles)} roles de verificación cargados")
        else:
            verification_roles = {}
    except Exception as e:
        print(f"❌ Error cargando roles de verificación: {e}")
        verification_roles = {}

def normalize_verification_roles(raw_roles):
    """Acepta configuraciones antiguas y nuevas de verificación."""
    normalized = {}
    for custom_id, config in raw_roles.items():
        if isinstance(config, dict):
            role_id = config.get('role_id')
            if role_id is None:
                continue
            normalized[custom_id] = {
                'role_id': int(role_id),
                'use_captcha': bool(config.get('use_captcha', True)),
                'channel_id': config.get('channel_id'),
                'message_id': config.get('message_id')
            }
        else:
            normalized[custom_id] = {
                'role_id': int(config),
                'use_captcha': True,
                'channel_id': None
            }
    return normalized

def save_verification_embeds():
    """Guarda los embeds de verificación"""
    try:
        write_json(VERIFICATION_EMBEDS_FILE, verification_embeds)
        print(f"✅ Embeds de verificación guardados")
    except Exception as e:
        print(f"❌ Error guardando embeds: {e}")

def load_verification_embeds():
    """Carga los embeds de verificación"""
    global verification_embeds
    try:
        if os.path.exists(VERIFICATION_EMBEDS_FILE):
            verification_embeds = read_json(VERIFICATION_EMBEDS_FILE, {})
            print(f"✅ Embeds de verificación cargados")
        else:
            verification_embeds = {}
            migrate_legacy_verification_embeds()
    except Exception as e:
        print(f"❌ Error cargando embeds: {e}")
        verification_embeds = {}

def migrate_legacy_verification_embeds():
    """Copia embeds de verificación antiguos desde data/embeds_storage.json."""
    if not os.path.exists(LEGACY_EMBEDS_STORAGE_FILE):
        return

    try:
        legacy_embeds = read_json(LEGACY_EMBEDS_STORAGE_FILE, {})

        migrated = 0
        for embed_id, data in legacy_embeds.items():
            title = str(data.get('title') or '').lower()
            description = str(data.get('description') or '').lower()
            looks_like_verification = (
                embed_id.startswith("verification_") or
                "verificación" in title or
                "verificacion" in title or
                "verificación" in description or
                "verificacion" in description
            )

            if looks_like_verification and embed_id not in verification_embeds:
                verification_embeds[embed_id] = data
                migrated += 1

        if migrated:
            save_verification_embeds()
            print(f"✅ {migrated} embeds de verificación antiguos migrados")
    except Exception as e:
        print(f"❌ Error migrando embeds de verificación antiguos: {e}")

def get_verification_config(verification_id):
    custom_id = f"verify_button_{verification_id}"
    return custom_id, verification_roles.get(custom_id)

def save_verification_buttons():
    """Guarda la configuración visual de botones de verificación."""
    try:
        write_json(VERIFICATION_BUTTONS_FILE, verification_buttons)
        print("✅ Botones de verificación guardados")
    except Exception as e:
        print(f"❌ Error guardando botones de verificación: {e}")

def load_verification_buttons():
    """Carga emojis de botones de verificación."""
    global verification_buttons
    try:
        if os.path.exists(VERIFICATION_BUTTONS_FILE):
            verification_buttons = read_json(VERIFICATION_BUTTONS_FILE, {})
            print(f"✅ {len(verification_buttons)} botones de verificación cargados")
        else:
            verification_buttons = {}
    except Exception as e:
        print(f"❌ Error cargando botones de verificación: {e}")
        verification_buttons = {}

def get_verification_button_emoji(verification_id):
    return verification_buttons.get(verification_id, {}).get("emoji", "✅")

def parse_button_emoji(emoji_text):
    if not emoji_text:
        return None
    try:
        return discord.PartialEmoji.from_str(emoji_text)
    except Exception:
        return emoji_text

class VerificationView(ResponsiveView):
    def __init__(self, role_id: int, custom_id: str = None, use_captcha: bool = False, button_emoji: str = "✅"):
        super().__init__(timeout=None)
        self.role_id = role_id
        self.use_captcha = use_captcha
        if custom_id:
            self.verify.custom_id = custom_id
        self.verify.emoji = parse_button_emoji(button_emoji)
    
    @discord.ui.button(label="Verificar", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message('Usa este boton dentro del servidor.', ephemeral=True)
            return
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message("❌ No se pudo encontrar el rol de verificación.", ephemeral=True)
            return
        
        if role in interaction.user.roles:
            await interaction.response.send_message("✅ Ya tienes el rol de verificación.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        bot_member = interaction.guild.me
        if not bot_member or not bot_member.guild_permissions.manage_roles or role.managed or role.is_default() or role >= bot_member.top_role:
            await interaction.followup.send(
                'No puedo asignar el rol. El bot necesita Gestionar roles y su rol debe estar por encima del rol de verificacion.',
                ephemeral=True,
            )
            return
        
        # Si usa captcha, generar código y enviarlo por MD cuando sea posible.
        if self.use_captcha:
            from captcha import create_captcha_code, build_captcha_embed_message, build_captcha_prompt_embed

            result = create_captcha_code(str(interaction.user.id), interaction.guild.id, role.id)
            if not result['success']:
                await interaction.followup.send(result['message'], ephemeral=True)
                return
            captcha_embed, captcha_file = await build_captcha_embed_message(interaction.user, interaction.guild, result)
            dm_sent = False

            try:
                dm_kwargs = {"embed": captcha_embed}
                if captcha_file:
                    dm_kwargs["file"] = captcha_file
                await interaction.user.send(**dm_kwargs)
                dm_sent = True
            except discord.HTTPException:
                dm_sent = False

            response_embed = build_captcha_prompt_embed(interaction.user, interaction.guild, dm_sent)

            if dm_sent:
                await interaction.followup.send(
                    embed=response_embed,
                    view=CaptchaEntryView(role.id),
                    ephemeral=True
                )
            else:
                fallback_embed, fallback_file = await build_captcha_embed_message(interaction.user, interaction.guild, result)
                fallback_kwargs = {
                    "embeds": [response_embed, fallback_embed],
                    "view": CaptchaEntryView(role.id),
                    "ephemeral": True
                }
                if fallback_file:
                    fallback_kwargs["file"] = fallback_file
                await interaction.followup.send(**fallback_kwargs)
        else:
            # Verificación directa sin captcha
            try:
                await interaction.user.add_roles(role)
                await interaction.followup.send(
                    f"✅ ¡Te has verificado correctamente! Se te ha asignado el rol {role.name}.",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.followup.send("❌ No tengo permisos para asignar roles.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send('No se pudo asignar el rol. Contacta al staff.', ephemeral=True)

class CaptchaEntryView(ResponsiveView):
    def __init__(self, role_id: int):
        super().__init__(timeout=180)
        self.role_id = role_id
        from captcha import get_captcha_entry_button_label, get_captcha_entry_button_emoji, parse_captcha_emoji

        self.enter_code.label = get_captcha_entry_button_label()
        self.enter_code.emoji = parse_captcha_emoji(get_captcha_entry_button_emoji())

    @discord.ui.button(label="Ingresar Código", style=discord.ButtonStyle.success)
    async def enter_code(self, interaction: discord.Interaction, button: discord.ui.Button):
        from captcha import CaptchaModal

        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message("❌ No se pudo encontrar el rol de verificación.", ephemeral=True)
            return

        await interaction.response.send_modal(CaptchaModal(role, interaction.user))

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
    
    def to_embed(self):
        embed = discord.Embed()
        
        if self.title:
            embed.title = self.title
        if self.description:
            embed.description = self.description
        if self.color:
            try:
                embed.color = int(self.color.replace("#", ""), 16)
            except:
                embed.color = discord.Color.green()
        
        if self.image_url:
            embed.set_image(url=self.image_url)
        if self.thumbnail_url:
            embed.set_thumbnail(url=self.thumbnail_url)
        
        if self.footer_text:
            embed.set_footer(text=self.footer_text, icon_url=self.footer_icon)
        
        if self.author_name:
            embed.set_author(name=self.author_name, icon_url=self.author_icon)
        
        for field in self.fields:
            embed.add_field(name=field["name"], value=field["value"], inline=field.get("inline", False))
        
        if self.timestamp:
            embed.timestamp = discord.utils.utcnow()
        
        return embed
    
    def from_dict(self, data):
        """Carga datos desde diccionario"""
        self.title = data.get('title')
        self.description = data.get('description')
        self.color = data.get('color')
        self.image_url = data.get('image_url')
        self.thumbnail_url = data.get('thumbnail_url')
        self.footer_text = data.get('footer_text')
        self.footer_icon = data.get('footer_icon')
        self.author_name = data.get('author_name')
        self.author_icon = data.get('author_icon')
        self.fields = data.get('fields', [])
        self.timestamp = data.get('timestamp', False)
        return self
    
    def to_dict(self):
        """Convierte a diccionario para guardar"""
        return {
            'title': self.title,
            'description': self.description,
            'color': self.color,
            'image_url': self.image_url,
            'thumbnail_url': self.thumbnail_url,
            'footer_text': self.footer_text,
            'footer_icon': self.footer_icon,
            'author_name': self.author_name,
            'author_icon': self.author_icon,
            'fields': self.fields,
            'timestamp': self.timestamp
        }

VERIFICATION_EDIT_OPTIONS = {
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

class EditVerificationEmbedView(ResponsiveView):
    def __init__(self, verification_id, embed_builder, user_id):
        super().__init__(timeout=300)
        self.verification_id = verification_id
        self.embed_builder = embed_builder
        self.user_id = user_id
        self.add_item(EditVerificationFieldSelect(verification_id, embed_builder, user_id))

    @discord.ui.button(label="⏰ Activar/Desactivar Timestamp", style=discord.ButtonStyle.secondary)
    async def toggle_timestamp(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Solo quien abrió el editor puede usarlo.", ephemeral=True)
            return

        self.embed_builder.timestamp = not self.embed_builder.timestamp
        verification_embeds[self.verification_id] = self.embed_builder.to_dict()
        save_verification_embeds()
        await interaction.response.edit_message(
            content=f"✅ **Timestamp {'activado' if self.embed_builder.timestamp else 'desactivado'}**\n**Preview de verificación `{self.verification_id}`:**",
            embed=self.embed_builder.to_embed(),
            view=EditVerificationEmbedView(self.verification_id, self.embed_builder, interaction.user.id)
        )

    @discord.ui.button(label="➕ Agregar Campo", style=discord.ButtonStyle.secondary)
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Solo quien abrió el editor puede usarlo.", ephemeral=True)
            return

        modal = AddVerificationFieldModal()
        modal.verification_id = self.verification_id
        modal.embed_builder = self.embed_builder
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🧹 Limpiar Campos", style=discord.ButtonStyle.danger)
    async def clear_fields(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Solo quien abrió el editor puede usarlo.", ephemeral=True)
            return

        self.embed_builder.fields = []
        verification_embeds[self.verification_id] = self.embed_builder.to_dict()
        save_verification_embeds()
        await interaction.response.edit_message(
            content=f"✅ **Campos eliminados**\n**Preview de verificación `{self.verification_id}`:**",
            embed=self.embed_builder.to_embed(),
            view=EditVerificationEmbedView(self.verification_id, self.embed_builder, interaction.user.id)
        )

    @discord.ui.button(label="Editar Emoji Botón", style=discord.ButtonStyle.secondary)
    async def edit_button_emoji(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Solo quien abrió el editor puede usarlo.", ephemeral=True)
            return

        modal = EditVerificationButtonEmojiModal(self.verification_id, get_verification_button_emoji(self.verification_id))
        modal.embed_builder = self.embed_builder
        await interaction.response.send_modal(modal)

class EditVerificationFieldSelect(discord.ui.Select):
    def __init__(self, verification_id, embed_builder, user_id):
        self.verification_id = verification_id
        self.embed_builder = embed_builder
        self.user_id = user_id
        options = [
            discord.SelectOption(label=label, description=description, value=field_type)
            for field_type, (label, description, _style, _max_length) in VERIFICATION_EDIT_OPTIONS.items()
        ]
        super().__init__(
            placeholder="Elige qué parte del embed quieres editar...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Solo quien abrió el editor puede usarlo.", ephemeral=True)
            return

        field_type = self.values[0]
        label, placeholder, style, max_length = VERIFICATION_EDIT_OPTIONS[field_type]
        modal = EditVerificationModal(label, getattr(self.embed_builder, field_type) or "", field_type, placeholder, style, max_length)
        modal.verification_id = self.verification_id
        modal.embed_builder = self.embed_builder
        await interaction.response.send_modal(modal)

class EditVerificationModal(discord.ui.Modal):
    def __init__(self, field_name, current_value, field_type, placeholder=None, style=None, max_length=None):
        super().__init__(title=f"Editar {field_name}")
        self.field_type = field_type
        self.text_input = discord.ui.TextInput(
            label=field_name,
            default=current_value,
            placeholder=placeholder,
            max_length=max_length or (4000 if field_type == "description" else 256),
            required=False,
            style=style or (discord.TextStyle.paragraph if field_type == "description" else discord.TextStyle.short)
        )
        self.add_item(self.text_input)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.text_input.value.strip()
        setattr(self.embed_builder, self.field_type, value or None)
        verification_embeds[self.verification_id] = self.embed_builder.to_dict()
        save_verification_embeds()
        await interaction.response.edit_message(
            content=f"✅ **{self.text_input.label} actualizado**\n**Preview de verificación `{self.verification_id}`:**",
            embed=self.embed_builder.to_embed(),
            view=EditVerificationEmbedView(self.verification_id, self.embed_builder, interaction.user.id)
        )

class AddVerificationFieldModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Agregar Campo")
        self.field_name = discord.ui.TextInput(label="Nombre", max_length=256, required=True)
        self.field_value = discord.ui.TextInput(label="Valor", max_length=1024, required=True, style=discord.TextStyle.paragraph)
        self.inline = discord.ui.TextInput(label="Inline (si/no)", default="no", max_length=2, required=False)
        self.add_item(self.field_name)
        self.add_item(self.field_value)
        self.add_item(self.inline)

    async def on_submit(self, interaction: discord.Interaction):
        self.embed_builder.fields.append({
            "name": self.field_name.value,
            "value": self.field_value.value,
            "inline": self.inline.value.lower() in ["si", "sí", "s", "yes", "y"]
        })
        verification_embeds[self.verification_id] = self.embed_builder.to_dict()
        save_verification_embeds()
        await interaction.response.edit_message(
            content=f"✅ **Campo agregado**\n**Preview de verificación `{self.verification_id}`:**",
            embed=self.embed_builder.to_embed(),
            view=EditVerificationEmbedView(self.verification_id, self.embed_builder, interaction.user.id)
        )

class EditVerificationButtonEmojiModal(discord.ui.Modal):
    def __init__(self, verification_id, current_emoji):
        super().__init__(title="Editar Emoji del Botón")
        self.verification_id = verification_id
        self.emoji_input = discord.ui.TextInput(
            label="Emoji del botón",
            default=current_emoji or "✅",
            placeholder="Ej: ✅ o <:verificar:123456789012345678>",
            max_length=100,
            required=True
        )
        self.add_item(self.emoji_input)

    async def on_submit(self, interaction: discord.Interaction):
        emoji = self.emoji_input.value.strip()
        verification_buttons[self.verification_id] = {"emoji": emoji}
        save_verification_buttons()

        await interaction.response.edit_message(
            content=f"✅ **Emoji del botón actualizado:** {emoji}\n**Preview de verificación `{self.verification_id}`:**",
            embed=self.embed_builder.to_embed(),
            view=EditVerificationEmbedView(self.verification_id, self.embed_builder, interaction.user.id)
        )

def setup_verification_commands(bot):
    """Configura los comandos de verificación"""
    verification_group = app_commands.Group(name="verificacion", description="Comandos avanzados de verificación")

    @bot.tree.command(name='verificacion_reparar', description='Vincula el boton de un mensaje antiguo al rol correcto sin cambiar el embed')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def verificacion_reparar(
        interaction: discord.Interaction, canal: discord.TextChannel,
        mensaje_id: str, rol: discord.Role, usar_captcha: bool = True,
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if canal.guild.id != interaction.guild.id or rol.guild.id != interaction.guild.id:
            await interaction.followup.send('El canal y el rol deben pertenecer a este servidor.', ephemeral=True)
            return
        try:
            message = await canal.fetch_message(int(mensaje_id))
        except (ValueError, discord.HTTPException):
            await interaction.followup.send('No pude leer el mensaje. Comprueba su ID y mis permisos para ver el canal y su historial.', ephemeral=True)
            return
        if message.author.id != bot.user.id:
            await interaction.followup.send('Solo puedo reparar mensajes enviados por este bot.', ephemeral=True)
            return
        candidates = [component for row in message.components for component in row.children
                      if isinstance(component, discord.Button) and component.custom_id
                      and (component.custom_id == 'verify_button' or component.custom_id.startswith('verify_button_'))]
        if len(candidates) != 1:
            await interaction.followup.send('El mensaje debe tener exactamente un boton de verificacion reconocible.', ephemeral=True)
            return
        button = candidates[0]
        custom_id = button.custom_id
        verification_roles[custom_id] = {
            'role_id': rol.id, 'use_captcha': usar_captcha,
            'channel_id': canal.id, 'message_id': message.id,
        }
        write_json(VERIFICATION_ROLES_FILE, verification_roles)
        from storage import storage
        if storage.pool:
            await asyncio.wait_for(storage.flush(), timeout=10)
        bot.add_view(VerificationView(rol.id, custom_id, usar_captcha, str(button.emoji) if button.emoji else None))
        await interaction.followup.send(
            f'Boton reparado: `{custom_id}`. Rol: {rol.mention}. Captcha: {usar_captcha}. El embed se conserva.',
            ephemeral=True,
        )

    @verification_group.command(name="edit_embed", description="Edita todas las partes de un embed de verificación")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(verification_id="ID guardado, ejemplo: verification_2")
    async def verificacion_edit_embed(interaction: discord.Interaction, verification_id: str):
        if verification_id not in verification_embeds:
            available = ", ".join(verification_embeds.keys()) or "ningún embed guardado"
            await interaction.response.send_message(
                f"❌ No existe el embed de verificación `{verification_id}`.\n"
                f"Disponibles: {available}",
                ephemeral=True
            )
            return

        builder = EmbedBuilder().from_dict(verification_embeds[verification_id])
        await interaction.response.send_message(
            f"🛠️ **Editando verificación `{verification_id}`**\n"
            "Usa el menú para elegir qué parte del embed quieres modificar.",
            embed=builder.to_embed(),
            view=EditVerificationEmbedView(verification_id, builder, interaction.user.id),
            ephemeral=True
        )
    
    @bot.tree.command(name="verificacion_setup", description="Configura el sistema de verificación con captcha")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        canal="Canal donde se enviará el mensaje de verificación",
        rol="Rol que se asignará al verificarse",
        usar_captcha="¿Usar sistema de captcha? (True/False)"
    )
    async def verificacion_setup(
        interaction: discord.Interaction,
        canal: discord.TextChannel,
        rol: discord.Role,
        usar_captcha: bool = True
    ):
        embed_builder = EmbedBuilder()
        
        await interaction.response.send_message(
            "🔧 **Configurando Sistema de Verificación**\n"
            f"Canal: {canal.mention}\n"
            f"Rol: {rol.mention}\n"
            f"Captcha: {'✅ Activado' if usar_captcha else '❌ Desactivado'}\n\n"
            "Responde las siguientes preguntas para personalizar el embed...",
            ephemeral=True
        )
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel
        
        try:
            # Título
            await interaction.followup.send("📝 **1/4** - ¿Cuál será el título del embed?", ephemeral=True)
            msg = await bot.wait_for('message', check=check, timeout=120.0)
            embed_builder.title = msg.content
            
            # Descripción
            await interaction.followup.send("📄 **2/4** - ¿Cuál será la descripción?", ephemeral=True)
            msg = await bot.wait_for('message', check=check, timeout=120.0)
            embed_builder.description = msg.content
            
            # Color
            await interaction.followup.send("🎨 **3/4** - ¿Qué color? (formato #00FF00 o 'skip' para verde)", ephemeral=True)
            msg = await bot.wait_for('message', check=check, timeout=120.0)
            if msg.content.lower() != 'skip':
                embed_builder.color = msg.content
            else:
                embed_builder.color = "#00FF00"
            
            # Imagen
            await interaction.followup.send("🖼️ **4/4** - URL de imagen (o 'skip')", ephemeral=True)
            msg = await bot.wait_for('message', check=check, timeout=120.0)
            if msg.content.lower() != 'skip':
                embed_builder.image_url = msg.content
            
            embed_builder.timestamp = True
            
            # Guardar configuración
            verification_id = f"verification_{len(verification_embeds) + 1}"
            custom_id = f"verify_button_{verification_id}"
            
            verification_embeds[verification_id] = embed_builder.to_dict()
            verification_buttons.setdefault(verification_id, {"emoji": "✅"})
            verification_roles[custom_id] = {
                'role_id': rol.id,
                'use_captcha': usar_captcha,
                'channel_id': canal.id
            }
            
            save_verification_embeds()
            save_verification_buttons()
            save_verification_roles()
            
            # Enviar embed con botón
            embed = embed_builder.to_embed()
            view = VerificationView(rol.id, custom_id, usar_captcha, get_verification_button_emoji(verification_id))
            
            await canal.send(embed=embed, view=view)
            await interaction.followup.send(
                f"✅ **Sistema de verificación configurado exitosamente**\n"
                f"📍 Canal: {canal.mention}\n"
                f"🎯 Rol: {rol.mention}\n"
                f"🔒 Captcha: {'Activado' if usar_captcha else 'Desactivado'}\n"
                f"🆔 ID: `{verification_id}`",
                ephemeral=True
            )
            
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Tiempo agotado. Configuración cancelada.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    @bot.tree.command(name="verificacion_enviar", description="Envía un embed de verificación guardado a un canal")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        canal="Canal donde se enviará la verificación",
        verification_id="ID guardado, ejemplo: verification_1",
        rol="Rol a asignar si el ID no tiene rol guardado o quieres reemplazarlo",
        usar_captcha="Usar captcha para esta verificación"
    )
    async def verificacion_enviar(
        interaction: discord.Interaction,
        canal: discord.TextChannel,
        verification_id: str,
        rol: Optional[discord.Role] = None,
        usar_captcha: Optional[bool] = None
    ):
        if verification_id not in verification_embeds:
            available = ", ".join(verification_embeds.keys()) or "ningún embed guardado"
            await interaction.response.send_message(
                f"❌ No existe el embed de verificación `{verification_id}`.\n"
                f"Disponibles: {available}",
                ephemeral=True
            )
            return

        custom_id, stored_config = get_verification_config(verification_id)
        role_id = rol.id if rol else (stored_config or {}).get('role_id')

        if role_id is None:
            await interaction.response.send_message(
                "❌ Ese embed no tiene rol guardado. Usa el parámetro `rol` para indicar qué rol debe asignar.",
                ephemeral=True
            )
            return

        captcha_enabled = usar_captcha if usar_captcha is not None else (stored_config or {}).get('use_captcha', True)

        builder = EmbedBuilder().from_dict(verification_embeds[verification_id])
        embed = builder.to_embed()
        view = VerificationView(int(role_id), custom_id, captcha_enabled, get_verification_button_emoji(verification_id))

        verification_roles[custom_id] = {
            'role_id': int(role_id),
            'use_captcha': bool(captcha_enabled),
            'channel_id': canal.id
        }
        save_verification_roles()

        try:
            await canal.send(embed=embed, view=view)
            await interaction.response.send_message(
                f"✅ Verificación `{verification_id}` enviada en {canal.mention}.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ No tengo permisos para enviar mensajes en {canal.mention}.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Error al enviar verificación: {e}", ephemeral=True)
    
    @bot.tree.command(name="verificacion_lista", description="Lista todas las configuraciones de verificación")
    async def verificacion_lista(interaction: discord.Interaction):
        if not verification_roles and not verification_embeds:
            await interaction.response.send_message("📝 No hay configuraciones de verificación.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📋 Configuraciones de Verificación",
            color=discord.Color.green()
        )
        
        for verification_id, embed_data in verification_embeds.items():
            custom_id, config = get_verification_config(verification_id)
            title = embed_data.get('title') or "Sin título"
            role = interaction.guild.get_role(config['role_id']) if config else None
            channel_id = config.get('channel_id') if config else None
            channel = interaction.guild.get_channel(channel_id) if channel_id else None
            captcha_status = "🔒 Con Captcha" if (config or {}).get('use_captcha', True) else "🔓 Sin Captcha"

            embed.add_field(
                name=f"ID: {verification_id}",
                value=f"Título: {title[:80]}\n"
                      f"Rol: {role.mention if role else 'No guardado'}\n"
                      f"Canal: {channel.mention if channel else 'No guardado'}\n"
                      f"Emoji botón: {get_verification_button_emoji(verification_id)}\n"
                      f"{captcha_status}",
                inline=False
            )

        listed_custom_ids = {f"verify_button_{verification_id}" for verification_id in verification_embeds}
        for custom_id, config in verification_roles.items():
            if custom_id in listed_custom_ids:
                continue
            role = interaction.guild.get_role(config['role_id'])
            channel_id = config.get('channel_id')
            channel = interaction.guild.get_channel(channel_id) if channel_id else None
            captcha_status = "🔒 Con Captcha" if config.get('use_captcha', False) else "🔓 Sin Captcha"
            verification_id = custom_id.replace("verify_button_", "", 1)
            
            embed.add_field(
                name=f"ID: {custom_id}",
                value=f"Rol: {role.mention if role else 'Eliminado'}\n"
                      f"Canal: {channel.mention if channel else 'No guardado'}\n"
                      f"Emoji botón: {get_verification_button_emoji(verification_id)}\n"
                      f"{captcha_status}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @verificacion_edit_embed.error
    async def verificacion_group_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Necesitas permisos de administrador para usar este comando.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)

    try:
        bot.tree.add_command(verification_group)
    except app_commands.CommandAlreadyRegistered:
        pass

async def restore_verification_views(bot):
    """Restaura las vistas de verificación después del reinicio"""
    load_verification_roles()
    load_verification_embeds()
    load_verification_buttons()
    
    for custom_id, config in verification_roles.items():
        try:
            use_captcha = config.get('use_captcha', False)
            verification_id = custom_id.replace("verify_button_", "", 1)
            bot.add_view(VerificationView(config['role_id'], custom_id, use_captcha, get_verification_button_emoji(verification_id)))
            print(f"✅ Vista de verificación restaurada: {custom_id}")
        except Exception as e:
            print(f"❌ Error restaurando vista {custom_id}: {e}")


async def respond_to_unregistered_verification(interaction):
    if interaction.type != discord.InteractionType.component:
        return
    custom_id = (interaction.data or {}).get('custom_id', '')
    if custom_id != 'verify_button' and not custom_id.startswith('verify_button_'):
        return
    registered = any(
        getattr(item, 'custom_id', None) == custom_id
        for view in interaction.client.persistent_views for item in view.children
    )
    logging.info('Verification click: custom_id=%s registered=%s', custom_id, registered)
    if registered or interaction.response.is_done():
        return
    await interaction.response.send_message(
        'Este panel antiguo no tiene su boton vinculado. Un administrador debe usar /verificacion_reparar sobre este mensaje.',
        ephemeral=True,
    )

def setup(bot):
    """Función principal para configurar el módulo de verificación"""
    print("🔧 Configurando sistema de verificación...")
    load_verification_roles()
    load_verification_embeds()
    load_verification_buttons()
    setup_verification_commands(bot)
    bot.add_listener(respond_to_unregistered_verification, 'on_interaction')
    print("✅ Sistema de verificación configurado")

    @bot.tree.error
    async def verification_global_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Necesitas permisos de administrador para usar este comando.", ephemeral=True)
        else:
            import logging
            logging.error('Slash command failed', exc_info=(type(error), error, error.__traceback__))
            try:
                if interaction.response.is_done():
                    await interaction.followup.send('No se pudo completar el comando. Contacta al staff.', ephemeral=True)
                else:
                    await interaction.response.send_message('No se pudo completar el comando. Contacta al staff.', ephemeral=True)
            except discord.HTTPException:
                pass
