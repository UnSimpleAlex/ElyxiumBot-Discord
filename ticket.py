import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import io
from typing import Optional
from datetime import datetime

from common import configure_console, ensure_data_dir, write_json, read_json, ResponsiveView, StudioEmbed


configure_console()

# Configuración del sistema de tickets
SUPPORT_ROLE_ID = int(os.getenv('SUPPORT_ROLE_ID', '0'))
TICKET_CATEGORY_ID = int(os.getenv('TICKET_CATEGORY_ID', '0'))
TRANSCRIPT_CHANNEL_ID = int(os.getenv('TRANSCRIPT_CHANNEL_ID', '0'))

# Archivos de persistencia
TICKET_CONFIGS_FILE = "data/ticket_configs.json"
ACTIVE_TICKETS_FILE = "data/active_tickets.json"
TICKET_OPTIONS_FILE = "data/ticket_options.json"

ensure_data_dir()

# Sistema de almacenamiento de configuraciones de tickets
ticket_configs = {}
active_tickets = {}
ticket_options = {
    "soporte": {
        "label": "Soporte Técnico",
        "description": "Ayuda con problemas técnicos",
        "emoji": "🛠️"
    },
    "consulta": {
        "label": "Consulta General",
        "description": "Información general del proyecto",
        "emoji": "💎"
    },
    "reportar": {
        "label": "Reportar Problema",
        "description": "Reportar un problema o bug",
        "emoji": "⚠️"
    },
    "sugerencia": {
        "label": "Sugerencia",
        "description": "Enviar una sugerencia o idea",
        "emoji": "📝"
    },
    "otro": {
        "label": "Otro",
        "description": "Cualquier otra consulta",
        "emoji": "❓"
    }
}

def save_ticket_configs():
    """Guarda las configuraciones de tickets en archivo JSON"""
    try:
        configs_data = {}
        for config_id, builder in ticket_configs.items():
            configs_data[config_id] = {
                'title': builder.title,
                'description': builder.description,
                'color': builder.color,
                'image_url': builder.image_url,
                'thumbnail_url': builder.thumbnail_url,
                'footer_text': builder.footer_text,
                'footer_icon': builder.footer_icon,
                'author_name': builder.author_name,
                'author_icon': builder.author_icon,
                'timestamp': builder.timestamp
            }
        
        write_json(TICKET_CONFIGS_FILE, configs_data)
        print(f"✅ Configuraciones de tickets guardadas en {TICKET_CONFIGS_FILE}")
    except Exception as e:
        print(f"❌ Error guardando configuraciones de tickets: {e}")

def load_ticket_configs():
    """Carga las configuraciones de tickets desde archivo JSON"""
    global ticket_configs
    try:
        configs_data = read_json(TICKET_CONFIGS_FILE, {})
        if configs_data:
            ticket_configs = {}
            for config_id, data in configs_data.items():
                builder = TicketBuilder()
                builder.title = data.get('title')
                builder.description = data.get('description')
                builder.color = data.get('color')
                builder.image_url = data.get('image_url')
                builder.thumbnail_url = data.get('thumbnail_url')
                builder.footer_text = data.get('footer_text')
                builder.footer_icon = data.get('footer_icon')
                builder.author_name = data.get('author_name')
                builder.author_icon = data.get('author_icon')
                builder.timestamp = data.get('timestamp', False)
                
                ticket_configs[config_id] = builder
            
            print(f"✅ {len(ticket_configs)} configuraciones de tickets cargadas desde {TICKET_CONFIGS_FILE}")
        else:
            print(f"ℹ️ No se encontró {TICKET_CONFIGS_FILE}, iniciando con configuraciones vacías")
    except Exception as e:
        print(f"❌ Error cargando configuraciones de tickets: {e}")
        ticket_configs = {}

def save_active_tickets():
    """Guarda los tickets activos en archivo JSON"""
    try:
        write_json(ACTIVE_TICKETS_FILE, active_tickets)
        print(f"✅ Tickets activos guardados en {ACTIVE_TICKETS_FILE}")
    except Exception as e:
        print(f"❌ Error guardando tickets activos: {e}")

def load_active_tickets():
    """Carga los tickets activos desde archivo JSON"""
    global active_tickets
    try:
        active_tickets = read_json(ACTIVE_TICKETS_FILE, {})
        if active_tickets:
            # Convertir keys de string a int
            active_tickets = {int(k): v for k, v in active_tickets.items()}
            print(f"✅ {len(active_tickets)} tickets activos cargados desde {ACTIVE_TICKETS_FILE}")
        else:
            print(f"ℹ️ No se encontró {ACTIVE_TICKETS_FILE}, iniciando con tickets vacíos")
            active_tickets = {}
    except Exception as e:
        print(f"❌ Error cargando tickets activos: {e}")
        active_tickets = {}

def save_ticket_options():
    """Guarda las opciones del selector de tickets."""
    try:
        write_json(TICKET_OPTIONS_FILE, ticket_options)
        print(f"✅ Opciones de tickets guardadas en {TICKET_OPTIONS_FILE}")
    except Exception as e:
        print(f"❌ Error guardando opciones de tickets: {e}")

def load_ticket_options():
    """Carga las opciones del selector sin romper valores por defecto."""
    global ticket_options
    try:
        if os.path.exists(TICKET_OPTIONS_FILE):
            stored_options = read_json(TICKET_OPTIONS_FILE, {})
            for key, option in stored_options.items():
                if key in ticket_options and isinstance(option, dict):
                    ticket_options[key].update(option)
            print(f"✅ Opciones de tickets cargadas desde {TICKET_OPTIONS_FILE}")
        else:
            save_ticket_options()
    except Exception as e:
        print(f"❌ Error cargando opciones de tickets: {e}")

def parse_select_emoji(emoji_text):
    """Acepta emojis unicode o personalizados como <:nombre:id>."""
    if not emoji_text:
        return None
    try:
        return discord.PartialEmoji.from_str(emoji_text)
    except Exception:
        return emoji_text

TICKET_OPTION_CHOICES = [
    app_commands.Choice(name="Soporte Técnico", value="soporte"),
    app_commands.Choice(name="Consulta General", value="consulta"),
    app_commands.Choice(name="Reportar Problema", value="reportar"),
    app_commands.Choice(name="Sugerencia", value="sugerencia"),
    app_commands.Choice(name="Otro", value="otro"),
]

class TicketBuilder:
    def __init__(self):
        self.title = "🎫 Sistema de Tickets - Elyxium Studio"
        self.description = "Selecciona una categoría para abrir un ticket de soporte"
        self.color = "#0099ff"
        self.image_url = None
        self.thumbnail_url = None
        self.footer_text = "Elyxium Studio - Soporte"
        self.footer_icon = None
        self.author_name = None
        self.author_icon = None
        self.timestamp = True
    
    def to_embed(self):
        embed = StudioEmbed()
        
        if self.title:
            embed.title = self.title
        if self.description:
            embed.description = self.description
        if self.color:
            try:
                embed.color = int(self.color.replace("#", ""), 16)
            except:
                embed.color = discord.Color.blue()
        
        if self.image_url:
            embed.set_image(url=self.image_url)
        if self.thumbnail_url:
            embed.set_thumbnail(url=self.thumbnail_url)
        
        if self.footer_text:
            embed.set_footer(text=self.footer_text, icon_url=self.footer_icon)
        
        if self.author_name:
            embed.set_author(name=self.author_name, icon_url=self.author_icon)
        
        if self.timestamp:
            embed.timestamp = discord.utils.utcnow()
        
        return embed

    def to_dict(self):
        info = {}
        if self.title: info['Título'] = self.title
        if self.description: info['Descripción'] = self.description[:100] + "..." if len(self.description) > 100 else self.description
        if self.color: info['Color'] = self.color
        if self.image_url: info['Imagen'] = self.image_url
        if self.thumbnail_url: info['Miniatura'] = self.thumbnail_url
        if self.footer_text: info['Footer'] = self.footer_text
        if self.author_name: info['Autor'] = self.author_name
        if self.timestamp: info['Timestamp'] = "Activado"
        return info

class TicketCategorySelect(discord.ui.Select):
    def __init__(self):
        options = []
        for value, option in ticket_options.items():
            options.append(discord.SelectOption(
                label=option.get("label", value.title()),
                description=option.get("description"),
                value=value,
                emoji=parse_select_emoji(option.get("emoji"))
            ))
        
        super().__init__(placeholder="Selecciona una categoría...", min_values=1, max_values=1, options=options, custom_id="ticket_category_select")

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message('Usa tickets dentro del servidor.', ephemeral=True)
            return
        key = (interaction.guild.id, interaction.user.id)
        pending = getattr(interaction.client, '_pending_tickets', None)
        if pending is None:
            pending = interaction.client._pending_tickets = set()
        if key in pending:
            await interaction.response.send_message('Tu ticket ya se esta creando.', ephemeral=True)
            return
        # Verificar si el usuario ya tiene un ticket abierto
        for channel_id, ticket_info in active_tickets.items():
            if ticket_info['user_id'] == interaction.user.id:
                channel = interaction.guild.get_channel(int(channel_id))
                if channel:
                    await interaction.response.send_message(f"❌ Ya tienes un ticket abierto: {channel.mention}", ephemeral=True)
                    return
        
        category = self.values[0]
        pending.add(key)
        try:
            await interaction.response.defer(ephemeral=True)
            await self.create_ticket(interaction, category)
        finally:
            pending.discard(key)

    async def create_ticket(self, interaction: discord.Interaction, category: str):
        guild = interaction.guild
        user = interaction.user
        
        ticket_category = None
        if TICKET_CATEGORY_ID != 0:
            ticket_category = guild.get_channel(TICKET_CATEGORY_ID)
        
        support_role = guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID != 0 else None
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True, embed_links=True)
        }
        
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True, manage_messages=True)
        
        try:
            channel_name = f"ticket-{user.display_name.lower().replace(' ', '-')}"
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=ticket_category,
                overwrites=overwrites,
                topic=f"Ticket de {user.mention} | Categoría: {category.title()}"
            )
            
            active_tickets[ticket_channel.id] = {
                'user_id': user.id,
                'category': category,
                'created_at': datetime.now().isoformat(),
                'status': 'open'
            }
            
            save_active_tickets()
            
            embed = self.create_category_embed(category, user)
            view = TicketControlView(ticket_channel.id)
            
            mention_text = f"{user.mention}"
            if support_role:
                mention_text += f" {support_role.mention}"
            
            await ticket_channel.send(content=mention_text, embed=embed, view=view)
            await interaction.followup.send(f"✅ Ticket creado exitosamente: {ticket_channel.mention}", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ No tengo permisos para crear canales de tickets.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send('No se pudo completar el ticket. Contacta al staff.', ephemeral=True)

    def create_category_embed(self, category: str, user: discord.Member):
        category_info = {
            "soporte": {
                "title": "🛠️ Soporte Técnico",
                "description": f"¡Hola {user.mention}! Gracias por contactarnos.\n\n**Por favor proporciona la siguiente información:**\n• **Descripción del problema:** Explica detalladamente el issue\n• **¿Cuándo ocurrió?** Fecha y hora aproximada\n• **Capturas de pantalla:** Si es posible, adjunta evidencia\n\nUn miembro del equipo te atenderá pronto.",
                "color": 0x00FF00
            },
            "consulta": {
                "title": "💎 Consulta General",
                "description": f"¡Hola {user.mention}! Estamos aquí para ayudarte.\n\n**Por favor describe:**\n• **Tu consulta:** Explica qué necesitas saber\n• **Información adicional:** Cualquier detalle relevante\n\nUn miembro del equipo responderá tus dudas pronto.",
                "color": 0xFFD700
            },
            "reportar": {
                "title": "⚠️ Reportar Problema",
                "description": f"¡Hola {user.mention}! Gracias por reportar.\n\n**Por favor proporciona:**\n• **Descripción del problema:** ¿Qué ocurrió?\n• **Pasos para reproducir:** ¿Cómo sucedió?\n• **Evidencia:** Capturas de pantalla o videos\n• **Fecha y hora:** ¿Cuándo ocurrió?\n\nEl equipo revisará tu reporte y tomará las medidas necesarias.",
                "color": 0xFF4444
            },
            "sugerencia": {
                "title": "📝 Sugerencia",
                "description": f"¡Hola {user.mention}! Nos encanta recibir sugerencias.\n\n**Por favor describe:**\n• **Tu sugerencia:** ¿Qué propones?\n• **Beneficios:** ¿Por qué sería útil?\n• **Detalles adicionales:** Cualquier información extra\n\nEl equipo evaluará tu propuesta.",
                "color": 0x9B59B6
            },
            "otro": {
                "title": "❓ Consulta General",
                "description": f"¡Hola {user.mention}! Estamos aquí para ayudarte.\n\n**Por favor describe:**\n• **Tu consulta o problema:** Explica detalladamente\n• **Información adicional:** Cualquier detalle relevante\n\nUn miembro del equipo te ayudará pronto.",
                "color": 0x95A5A6
            }
        }
        
        info = category_info.get(category, category_info["otro"])
        embed = StudioEmbed(title=info["title"], description=info["description"], color=info["color"], timestamp=discord.utils.utcnow())
        embed.set_footer(text="Elyxium Studio - Sistema de Tickets", icon_url=user.guild.icon.url if user.guild.icon else None)
        return embed

class TicketControlView(ResponsiveView):
    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        # Usar custom_id persistente basado en el channel_id
        self.close_ticket.custom_id = f"close_ticket_{channel_id}"
        self.generate_transcript.custom_id = f"transcript_ticket_{channel_id}"

    @discord.ui.button(label="🔒 Cerrar Ticket", style=discord.ButtonStyle.danger)
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        support_role = interaction.guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID != 0 else None
        if not (interaction.user.guild_permissions.administrator or 
                (support_role and support_role in interaction.user.roles) or
                (self.channel_id in active_tickets and active_tickets[self.channel_id]['user_id'] == interaction.user.id)):
            await interaction.response.send_message("❌ Solo el usuario del ticket o el staff puede cerrar el ticket.", ephemeral=True)
            return
        
        confirm_view = ConfirmCloseView(self.channel_id)
        await interaction.response.send_message("🔒 **¿Estás seguro de que quieres cerrar este ticket?**\nEsta acción no se puede deshacer.", view=confirm_view, ephemeral=True)

    @discord.ui.button(label="📋 Transcript", style=discord.ButtonStyle.secondary)
    async def generate_transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        support_role = interaction.guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID != 0 else None
        if not (interaction.user.guild_permissions.administrator or (support_role and support_role in interaction.user.roles)):
            await interaction.response.send_message("❌ Solo el staff puede generar transcripts.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        channel = interaction.channel
        messages = []
        
        async for message in channel.history(limit=5000, oldest_first=True):
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            content = message.content or "[Contenido multimedia/embed]"
            messages.append(f"[{timestamp}] {message.author}: {content}")
        
        transcript_content = "\n".join(messages)
        
        file_content = f"TRANSCRIPT DEL TICKET - {channel.name}\n"
        file_content += f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        file_content += "="*50 + "\n\n"
        file_content += transcript_content
        
        file = discord.File(fp=io.BytesIO(file_content.encode('utf-8')), filename=f"transcript-{channel.name}.txt")
        await interaction.followup.send("📋 Transcript generado:", file=file, ephemeral=True)

class ConfirmCloseView(ResponsiveView):
    def __init__(self, channel_id: int):
        super().__init__(timeout=30)
        self.channel_id = channel_id

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        info = active_tickets.get(self.channel_id)
        support = interaction.guild.get_role(SUPPORT_ROLE_ID) if interaction.guild else None
        if not info or interaction.channel_id != self.channel_id or not (
            interaction.user.guild_permissions.administrator
            or (support and support in interaction.user.roles)
            or info['user_id'] == interaction.user.id
        ):
            await interaction.response.send_message('No tienes permiso para cerrar este ticket.', ephemeral=True)
            return
        channel = interaction.channel
        
        if self.channel_id in active_tickets:
            ticket_info = active_tickets[self.channel_id]
            user = interaction.guild.get_member(ticket_info['user_id'])
            
            close_embed = StudioEmbed(title="🔒 Ticket Cerrado", description=f"Ticket cerrado por {interaction.user.mention}", color=0xFF0000, timestamp=discord.utils.utcnow())
            close_embed.add_field(name="Usuario", value=user.mention if user else "Usuario no encontrado", inline=True)
            close_embed.add_field(name="Categoría", value=ticket_info['category'].title(), inline=True)
            close_embed.add_field(name="Duración", value=f"Creado: <t:{int(datetime.fromisoformat(ticket_info['created_at']).timestamp())}:R>", inline=True)
            
            await interaction.response.send_message(embed=close_embed)
            
            del active_tickets[self.channel_id]
            save_active_tickets()
            
            await asyncio.sleep(5)
            await channel.delete(reason=f"Ticket cerrado por {interaction.user}")
        else:
            await interaction.response.send_message("❌ Error al cerrar el ticket.", ephemeral=True)

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Cierre de ticket cancelado.", ephemeral=True)
        self.stop()

class TicketSelectView(ResponsiveView):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect())

TICKET_EDIT_OPTIONS = {
    "title": ("Título", "Título del panel de tickets", discord.TextStyle.short, 256),
    "description": ("Descripción", "Descripción del panel de tickets", discord.TextStyle.paragraph, 4000),
    "color": ("Color", "Color hexadecimal, ejemplo: #0099ff", discord.TextStyle.short, 7),
    "image_url": ("Imagen", "URL de la imagen principal", discord.TextStyle.short, 1000),
    "thumbnail_url": ("Miniatura", "URL de la miniatura", discord.TextStyle.short, 1000),
    "footer_text": ("Footer", "Texto del footer", discord.TextStyle.short, 2048),
    "footer_icon": ("Icono footer", "URL del icono del footer", discord.TextStyle.short, 1000),
    "author_name": ("Autor", "Nombre del autor", discord.TextStyle.short, 256),
    "author_icon": ("Icono autor", "URL del icono del autor", discord.TextStyle.short, 1000),
}

class EditTicketEmbedView(ResponsiveView):
    def __init__(self, config_id, ticket_builder, user_id):
        super().__init__(timeout=300)
        self.config_id = config_id
        self.ticket_builder = ticket_builder
        self.user_id = user_id
        self.add_item(EditTicketFieldSelect(config_id, ticket_builder, user_id))
    
    @discord.ui.button(label="⏰ Activar/Desactivar Timestamp", style=discord.ButtonStyle.secondary)
    async def toggle_timestamp(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Solo quien configuró el ticket puede editarlo.", ephemeral=True)
            return

        self.ticket_builder.timestamp = not self.ticket_builder.timestamp
        ticket_configs[self.config_id] = self.ticket_builder
        save_ticket_configs()
        await interaction.response.edit_message(
            content=f"✅ **Timestamp {'activado' if self.ticket_builder.timestamp else 'desactivado'}**\n**Preview del ticket `{self.config_id}`:**",
            embed=self.ticket_builder.to_embed(),
            view=EditTicketEmbedView(self.config_id, self.ticket_builder, interaction.user.id)
        )

class EditTicketFieldSelect(discord.ui.Select):
    def __init__(self, config_id, ticket_builder, user_id):
        self.config_id = config_id
        self.ticket_builder = ticket_builder
        self.user_id = user_id
        options = [
            discord.SelectOption(label=label, description=description, value=field_type)
            for field_type, (label, description, _style, _max_length) in TICKET_EDIT_OPTIONS.items()
        ]
        super().__init__(
            placeholder="Elige qué parte del panel de tickets quieres editar...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Solo quien configuró el ticket puede editarlo.", ephemeral=True)
            return

        field_type = self.values[0]
        label, placeholder, style, max_length = TICKET_EDIT_OPTIONS[field_type]
        modal = EditTicketModal(label, getattr(self.ticket_builder, field_type) or "", field_type, placeholder, style, max_length)
        modal.ticket_builder = self.ticket_builder
        modal.config_id = self.config_id
        await interaction.response.send_modal(modal)

class EditTicketModal(discord.ui.Modal):
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
        setattr(self.ticket_builder, self.field_type, value or None)
        ticket_configs[self.config_id] = self.ticket_builder
        save_ticket_configs()
        
        preview_embed = self.ticket_builder.to_embed()
        view = EditTicketEmbedView(self.config_id, self.ticket_builder, interaction.user.id)
        
        await interaction.response.edit_message(
            content=f"✅ **{self.text_input.label} actualizado**\n**Preview del ticket `{self.config_id}`:**",
            embed=preview_embed,
            view=view
        )

# Funciones auxiliares
def is_admin():
    def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True
        admin_role_id = int(os.getenv('ADMIN_ROLE_ID', '0'))
        return any(role.id == admin_role_id for role in interaction.user.roles)
    return app_commands.check(predicate)

async def handle_file_upload(message, ticket_builder, field_type):
    if message.attachments:
        attachment = message.attachments[0]
        if attachment.content_type and (attachment.content_type.startswith('image/') or 
                                      attachment.filename.lower().endswith(('.gif', '.png', '.jpg', '.jpeg', '.webp', '.svg'))):
            setattr(ticket_builder, field_type, attachment.url)
            file_type = "GIF" if attachment.filename.lower().endswith('.gif') else "imagen"
            return f"📎 **{file_type.capitalize()} subida:** {attachment.filename}"
    return None

async def show_ticket_preview(channel, ticket_builder, config_id, step_info=""):
    preview_embed = ticket_builder.to_embed()
    info_dict = ticket_builder.to_dict()
    
    if info_dict:
        info_text = "\n".join([f"**{k}:** {v}" for k, v in info_dict.items()])
    else:
        info_text = "*Configuración vacía*"
    
    content = f"🎫 **Configurando Sistema de Tickets `{config_id}`**\n{step_info}\n\n📋 **Configuración actual:**\n{info_text}\n\n**Vista previa:**"
    
    try:
        return await channel.send(content=content, embed=preview_embed)
    except:
        return await channel.send(content=content + "\n*Error al mostrar preview - embed inválido*")

# FUNCIÓN PRINCIPAL - Configurar todos los comandos
def setup_ticket_commands(bot):
    ticket_group = app_commands.Group(name="ticket", description="Comandos avanzados del sistema de tickets")

    @ticket_group.command(name="edit_embed", description="Edita todas las partes de un embed de tickets guardado")
    @app_commands.describe(config_id="ID de la configuración, ejemplo: ticket_1")
    @is_admin()
    async def ticket_edit_embed(interaction: discord.Interaction, config_id: str):
        if config_id not in ticket_configs:
            available_configs = ", ".join(ticket_configs.keys()) or "ninguna configuración guardada"
            await interaction.response.send_message(
                f"❌ No se encontró la configuración `{config_id}`.\n"
                f"Configuraciones disponibles: {available_configs}",
                ephemeral=True
            )
            return

        ticket_builder = ticket_configs[config_id]
        await interaction.response.send_message(
            f"🛠️ **Editando sistema de tickets `{config_id}`**\n"
            "Usa el menú para elegir qué parte del embed quieres modificar.",
            embed=ticket_builder.to_embed(),
            view=EditTicketEmbedView(config_id, ticket_builder, interaction.user.id),
            ephemeral=True
        )

    @ticket_group.command(name="options", description="Muestra los emojis actuales de las opciones de tickets")
    @is_admin()
    async def ticket_options_command(interaction: discord.Interaction):
        embed = StudioEmbed(
            title="🎫 Opciones del selector de tickets",
            color=discord.Color.blue()
        )

        for value, option in ticket_options.items():
            emoji = option.get("emoji") or "Sin emoji"
            embed.add_field(
                name=f"{emoji} {option.get('label', value.title())}",
                value=f"ID: `{value}`\nDescripción: {option.get('description', 'Sin descripción')}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ticket_group.command(name="edit_options", description="Cambia los emojis del selector de tickets")
    @app_commands.describe(
        soporte="Emoji para Soporte Técnico. Ej: 🛠️ o <:soporte:123>",
        consulta="Emoji para Consulta General. Ej: 💎 o <:consulta:123>",
        reportar="Emoji para Reportar Problema. Ej: ⚠️ o <:reportar:123>",
        sugerencia="Emoji para Sugerencia. Ej: 📝 o <:sugerencia:123>",
        otro="Emoji para Otro. Ej: ❓ o <:otro:123>"
    )
    @is_admin()
    async def ticket_edit_options(
        interaction: discord.Interaction,
        soporte: Optional[str] = None,
        consulta: Optional[str] = None,
        reportar: Optional[str] = None,
        sugerencia: Optional[str] = None,
        otro: Optional[str] = None
    ):
        updates = {
            "soporte": soporte,
            "consulta": consulta,
            "reportar": reportar,
            "sugerencia": sugerencia,
            "otro": otro
        }

        changed = []
        for key, emoji in updates.items():
            if emoji is not None:
                ticket_options[key]["emoji"] = emoji
                changed.append(f"`{key}` → {emoji}")

        if not changed:
            await interaction.response.send_message(
                "ℹ️ No cambiaste ningún emoji. Usa `/ticket options` para ver la configuración actual.",
                ephemeral=True
            )
            return

        save_ticket_options()
        await interaction.response.send_message(
            "✅ Emojis de tickets actualizados:\n" + "\n".join(changed),
            ephemeral=True
        )

    @ticket_group.command(name="set_emoji", description="Cambia un emoji enviándolo en el chat")
    @app_commands.describe(opcion="Opción del selector que quieres modificar")
    @app_commands.choices(opcion=TICKET_OPTION_CHOICES)
    @is_admin()
    async def ticket_set_emoji(interaction: discord.Interaction, opcion: app_commands.Choice[str]):
        option_key = opcion.value
        option = ticket_options[option_key]

        await interaction.response.send_message(
            f"Envía ahora en este canal el emoji para **{option.get('label', option_key.title())}**.\n"
            "Puede ser un emoji normal o uno personalizado de Discord.",
            ephemeral=True
        )

        def check(message):
            return message.author.id == interaction.user.id and message.channel.id == interaction.channel.id

        try:
            message = await bot.wait_for('message', check=check, timeout=60.0)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Tiempo agotado. No se cambió ningún emoji.", ephemeral=True)
            return

        emoji = message.content.strip()
        if not emoji:
            await interaction.followup.send("❌ No detecté ningún emoji en tu mensaje.", ephemeral=True)
            return

        ticket_options[option_key]["emoji"] = emoji
        save_ticket_options()

        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        await interaction.followup.send(
            f"✅ Emoji actualizado: `{option_key}` → {emoji}",
            ephemeral=True
        )

    @ticket_group.command(name="set_option_text", description="Cambia el título o descripción de una opción")
    @app_commands.describe(
        opcion="Opción del selector que quieres modificar",
        parte="Qué texto quieres cambiar"
    )
    @app_commands.choices(
        opcion=TICKET_OPTION_CHOICES,
        parte=[
            app_commands.Choice(name="Título", value="label"),
            app_commands.Choice(name="Descripción", value="description"),
        ]
    )
    @is_admin()
    async def ticket_set_option_text(
        interaction: discord.Interaction,
        opcion: app_commands.Choice[str],
        parte: app_commands.Choice[str]
    ):
        option_key = opcion.value
        field = parte.value
        option = ticket_options[option_key]
        field_name = "título" if field == "label" else "descripción"
        max_length = 100 if field == "label" else 100

        await interaction.response.send_message(
            f"Envía ahora en este canal el nuevo **{field_name}** para **{option.get('label', option_key.title())}**.\n"
            f"Máximo recomendado: **{max_length} caracteres**.",
            ephemeral=True
        )

        def check(message):
            return message.author.id == interaction.user.id and message.channel.id == interaction.channel.id

        try:
            message = await bot.wait_for('message', check=check, timeout=90.0)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Tiempo agotado. No se cambió ningún texto.", ephemeral=True)
            return

        new_text = message.content.strip()
        if not new_text:
            await interaction.followup.send("❌ El texto no puede estar vacío.", ephemeral=True)
            return

        if len(new_text) > max_length:
            await interaction.followup.send(
                f"❌ El texto es demasiado largo. Discord permite máximo {max_length} caracteres en esa parte.",
                ephemeral=True
            )
            return

        ticket_options[option_key][field] = new_text
        save_ticket_options()

        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        await interaction.followup.send(
            f"✅ {field_name.title()} actualizado para `{option_key}`:\n{new_text}",
            ephemeral=True
        )

    @bot.tree.command(name="ticket_config", description="Configura un nuevo sistema de tickets personalizado")
    @is_admin()
    async def ticket_config(interaction: discord.Interaction):
        ticket_builder = TicketBuilder()
        config_id = f"ticket_{len(ticket_configs) + 1}"
        
        await interaction.response.send_message("🎫 **Configuración de Sistema de Tickets Iniciada**\nSe mostrará una vista previa en tiempo real. Responde con texto, URLs o sube archivos. Escribe 'skip' para saltar.", ephemeral=True)
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel
        
        preview_msg = await show_ticket_preview(interaction.channel, ticket_builder, config_id, "⏳ Esperando configuración...")
        
        try:
            steps = [
                ("título", "title", "📝 ¿Cuál será el título del embed de tickets?"),
                ("descripción", "description", "📄 ¿Cuál será la descripción del embed?"),
                ("color", "color", "🎨 ¿Qué color? (formato: #0099ff o skip para azul)"),
                ("imagen", "image_url", "🖼️ ¿Imagen principal? (sube archivo, URL, o skip)"),
                ("miniatura", "thumbnail_url", "🔳 ¿Imagen miniatura? (sube archivo, URL, o skip)"),
                ("footer", "footer_text", "👇 ¿Texto del footer? (o skip)"),
                ("icono footer", "footer_icon", "🔗 ¿Icono del footer? (sube archivo, URL, o skip)"),
                ("timestamp", "timestamp", "⏰ ¿Agregar timestamp? (si/no)")
            ]
            
            for i, (name, attr, question) in enumerate(steps, 1):
                await interaction.followup.send(f"**{i}/8** {question}", ephemeral=True)
                msg = await bot.wait_for('message', check=check, timeout=120.0)
                
                if msg.content.lower() != 'skip':
                    if attr in ['image_url', 'thumbnail_url', 'footer_icon']:
                        file_info = await handle_file_upload(msg, ticket_builder, attr)
                        if not file_info and msg.content:
                            setattr(ticket_builder, attr, msg.content)
                            file_info = "🔗 URL agregada"
                    elif attr == 'timestamp':
                        ticket_builder.timestamp = msg.content.lower() not in ['no', 'n']
                    else:
                        setattr(ticket_builder, attr, msg.content)
                    
                    await preview_msg.delete()
                    status = f"✅ {name.title()} configurado"
                    if attr in ['image_url', 'thumbnail_url', 'footer_icon'] and 'file_info' in locals():
                        status += f" {file_info or ''}"
                    preview_msg = await show_ticket_preview(interaction.channel, ticket_builder, config_id, status)
            
            ticket_configs[config_id] = ticket_builder
            save_ticket_configs()
            
            final_embed = ticket_builder.to_embed()
            view = EditTicketEmbedView(config_id, ticket_builder, interaction.user.id)
            
            await preview_msg.delete()
            await interaction.channel.send(
                f"✅ **Sistema de Tickets `{config_id}` configurado exitosamente**\n**Puedes editarlo usando los botones de abajo:**",
                embed=final_embed,
                view=view
            )
            
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Tiempo agotado. Configuración cancelada.", ephemeral=True)
    
    @bot.tree.command(name="ticket_enviar", description="Envía el sistema de tickets a un canal")
    @is_admin()
    async def ticket_enviar(interaction: discord.Interaction, canal: discord.TextChannel, config_id: str = "default"):
        if config_id == "default":
            ticket_builder = TicketBuilder()
        elif config_id not in ticket_configs:
            await interaction.response.send_message(f"❌ No se encontró la configuración `{config_id}`", ephemeral=True)
            return
        else:
            ticket_builder = ticket_configs[config_id]
        
        try:
            embed = ticket_builder.to_embed()
            view = TicketSelectView()
            
            await canal.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Sistema de tickets enviado al canal {canal.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ No tengo permisos para enviar mensajes en {canal.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error al enviar: {e}", ephemeral=True)
    
    @bot.tree.command(name="ticket_stats", description="Muestra estadísticas de tickets")
    @is_admin()
    async def ticket_stats(interaction: discord.Interaction):
        total_configs = len(ticket_configs)
        active_count = len(active_tickets)
        
        category_counts = {}
        for ticket_info in active_tickets.values():
            category = ticket_info['category']
            category_counts[category] = category_counts.get(category, 0) + 1
        
        embed = StudioEmbed(title="📊 Estadísticas de Tickets", color=0x0099FF, timestamp=discord.utils.utcnow())
        embed.add_field(name="📋 Configuraciones", value=f"{total_configs} configuraciones guardadas", inline=True)
        embed.add_field(name="🎫 Tickets Activos", value=f"{active_count} tickets abiertos", inline=True)
        
        if category_counts:
            category_text = []
            for category, count in category_counts.items():
                emoji_map = {'soporte': '🛠️', 'consulta': '💎', 'reportar': '⚠️', 'sugerencia': '📝', 'otro': '❓'}
                emoji = emoji_map.get(category, '❓')
                category_text.append(f"{emoji} {category.title()}: {count}")
            
            embed.add_field(name="📈 Por Categoría", value="\n".join(category_text), inline=False)
        
        embed.set_footer(text="Elyxium Studio - Sistema de Tickets")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Error handlers
    @ticket_options_command.error
    @ticket_edit_options.error
    @ticket_set_emoji.error
    @ticket_set_option_text.error
    @ticket_edit_embed.error
    @ticket_config.error
    @ticket_enviar.error
    @ticket_stats.error
    async def ticket_slash_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ No tienes permisos para usar este comando.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)

    try:
        bot.tree.add_command(ticket_group)
    except app_commands.CommandAlreadyRegistered:
        pass

# Función principal de configuración
def setup(bot):
    # Cargar datos al inicializar
    print("🔄 Cargando datos persistentes del sistema de tickets...")
    load_ticket_configs()
    load_active_tickets()
    load_ticket_options()
    
    # Restaurar las vistas persistentes de tickets
    print("🔄 Restaurando vistas de tickets...")
    bot.add_view(TicketSelectView())
    
    # Restaurar vistas de control para tickets activos
    for channel_id in active_tickets.keys():
        bot.add_view(TicketControlView(channel_id))
    
    print(f"✅ {len(active_tickets)} vistas de control de tickets restauradas")
    
    setup_ticket_commands(bot)
    print("✅ Sistema de Tickets Elyxium Studio con persistencia cargado correctamente")
