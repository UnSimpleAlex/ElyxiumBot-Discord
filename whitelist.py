"""Persistent community nickname registry, not a Minecraft server integration."""
import asyncio
import io
import logging
import re
import time

import discord
from discord import app_commands

from common import ResponsiveView, SERVER_EMOJIS, StudioEmbed, read_json, write_json


CONFIG_FILE = 'data/whitelist_config.json'
STATE_FILE = 'data/whitelist_members.json'
BANNER = 'https://res.cloudinary.com/y08rn1qr/image/upload/v1791077639/b5ab7ef8-d580-4e38-85d8-1e1e454b0ab3.png'
PAGE_SIZE = 9
NUMBER_EMOJIS = (
    '<:1473046951636242580:1555815284118659203>',
    '<:1473046979167916233:1555815281807458416>',
    '<:1473047000592158977:1555815279693529200>',
    '<:1473047026274144399:1555815277063704616>',
    '<:1473047061065765036:1555815274517762048>',
    '<:1473047092904857710:1555815272357568565>',
    '<:1473047114295804038:1555815270109417533>',
    '<:1473047140812198038:1555815267295174718>',
    '<:1473047167017943192:1555815265038762035>',
)


def validate_nickname(nickname):
    if not re.fullmatch(r'[A-Za-z0-9_]{3,16}', nickname):
        raise ValueError('El nickname Java debe tener entre 3 y 16 caracteres: letras, números o guion bajo, sin espacios.')
    return nickname


def render_panel(members, page=0):
    records = list(members.items())
    pages = max(1, (len(records) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(page, 0), pages - 1)
    description = (f"{SERVER_EMOJIS['community']} **TU LUGAR EN ELYXIUM STUDIO**\n\n"
                   'Registra tu **NICKNAME DE MINECRAFT JAVA** para formar parte de nuestra lista. '
                   'Cada usuario de Discord puede registrar **UN SOLO NICKNAME**.\n\n'
                   '**JUGADORES REGISTRADOS**\n')
    selected = records[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    if selected:
        description += '\n'.join(f'{NUMBER_EMOJIS[index]} `{record["nickname"]}` · <@{user_id}>'
                                 for index, (user_id, record) in enumerate(selected))
    else:
        description += 'La lista está vacía. Sé el primero en registrarte.'
    description += f'\n\n**REGISTRADOS:** {len(records)} · **PÁGINA:** {page + 1}/{pages}'
    embed = StudioEmbed(title=f"{SERVER_EMOJIS['shield']} 𝚆𝙷𝙸𝚃𝙴𝙻𝙸𝚂𝚃 · 𝙴𝙻𝚈𝚇𝙸𝚄𝙼 𝚂𝚃𝚄𝙳𝙸𝙾",
                        description=description, color=0x2ECC71)
    embed.set_image(url=BANNER)
    return embed, page, pages


class WhitelistService:
    def __init__(self, bot):
        self.bot = bot
        self.config = read_json(CONFIG_FILE, {})
        self.members = read_json(STATE_FILE, {})
        self.lock = asyncio.Lock()
        self.views = {}
        self.page_times = {}

    def valid_panel(self, interaction):
        config = self.config.get(str(interaction.guild_id), {})
        return (interaction.guild is not None and isinstance(interaction.user, discord.Member)
                and interaction.user.guild.id == interaction.guild_id
                and config.get('enabled') and interaction.channel_id == config.get('channel_id')
                and interaction.message.id == config.get('message_id'))

    def change(self, guild_id, user_id, nickname, editing=False, actor_id=None):
        nickname = validate_nickname(nickname)
        members = self.members.setdefault(str(guild_id), {})
        key = str(user_id)
        if not editing and key in members:
            raise ValueError('Este usuario ya tiene un nickname registrado. El staff puede editarlo.')
        if editing and key not in members:
            raise ValueError('Este usuario no tiene un nickname registrado.')
        if any(other_id != key and record['nickname'].lower() == nickname.lower()
               for other_id, record in members.items()):
            raise ValueError('Ese nickname ya está registrado por otro usuario.')
        if key not in members and len(members) >= 10000:
            raise ValueError('La lista alcanzó su capacidad. Contacta al staff.')
        previous = members.get(key, {})
        members[key] = {**previous, 'nickname': nickname, 'created_at': previous.get('created_at', time.time()),
                        'updated_at': time.time(), 'updated_by': actor_id or user_id}
        write_json(STATE_FILE, self.members)

    def export(self, guild_id, lowercase=False):
        names = [record['nickname'] for record in self.members.get(str(guild_id), {}).values()]
        return '\n'.join(name.lower() if lowercase else name for name in names)

    def restore(self):
        for guild_id, config in self.config.items():
            if config.get('enabled') and config.get('message_id'):
                view = WhitelistView(self, int(guild_id), config.get('page', 0))
                self.views[int(guild_id)] = view
                self.bot.add_view(view, message_id=config['message_id'])

    async def sync(self, guild_id):
        config = self.config[str(guild_id)]
        channel = self.bot.get_channel(config['channel_id']) or await self.bot.fetch_channel(config['channel_id'])
        embed, page, pages = render_panel(self.members.get(str(guild_id), {}), config.get('page', 0))
        view = WhitelistView(self, guild_id, page)
        view.previous.disabled, view.next.disabled = page == 0, page + 1 >= pages
        old_id, old_channel_id = config.get('message_id'), config.get('panel_channel_id', config['channel_id'])
        message = None
        if old_id and old_channel_id == channel.id:
            try:
                message = await channel.fetch_message(old_id)
                await message.edit(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
            except discord.NotFound:
                message = None
        if message is None:
            message = await channel.send(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
        previous = self.views.get(guild_id)
        if previous:
            previous.stop()
        self.views[guild_id] = view
        config.update(message_id=message.id, panel_channel_id=channel.id, page=page)
        write_json(CONFIG_FILE, self.config)
        if old_id and old_channel_id != channel.id:
            try:
                old_channel = self.bot.get_channel(old_channel_id) or await self.bot.fetch_channel(old_channel_id)
                await old_channel.get_partial_message(old_id).delete()
            except discord.NotFound:
                pass
            except discord.HTTPException:
                logging.exception('Could not remove retired whitelist panel')

    async def safe_sync(self, guild_id):
        try:
            await self.sync(guild_id)
            return True
        except discord.HTTPException:
            logging.exception('Whitelist saved but panel update failed')
            return False

    async def on_ready(self):
        async with self.lock:
            for guild_id, config in self.config.items():
                if config.get('enabled'):
                    await self.safe_sync(int(guild_id))


class WhitelistView(ResponsiveView):
    def __init__(self, service, guild_id, page=0):
        super().__init__(timeout=None)
        self.service, self.guild_id, self.page = service, guild_id, page
        self.register.emoji = discord.PartialEmoji.from_str(SERVER_EMOJIS['check'])
        self.previous.emoji = discord.PartialEmoji.from_str(SERVER_EMOJIS['document'])
        self.next.emoji = discord.PartialEmoji.from_str(SERVER_EMOJIS['pencil'])

    @discord.ui.button(label='Whitelist', style=discord.ButtonStyle.success, custom_id='whitelist:register')
    async def register(self, interaction, button):
        if interaction.guild_id != self.guild_id or not self.service.valid_panel(interaction):
            await interaction.response.send_message('Usa el panel actual del servidor.', ephemeral=True)
            return
        existing = self.service.members.get(str(self.guild_id), {}).get(str(interaction.user.id))
        if existing:
            await interaction.response.send_message(f'Ya registraste `{existing["nickname"]}`. Para cambiarlo, contacta al staff.', ephemeral=True)
            return
        await interaction.response.send_modal(NicknameModal(self.service, interaction))

    async def turn_page(self, interaction, delta):
        await interaction.response.defer(ephemeral=True)
        async with self.service.lock:
            if interaction.guild_id != self.guild_id or not self.service.valid_panel(interaction):
                await interaction.followup.send('Este panel ya no está activo.', ephemeral=True)
                return
            now = time.monotonic()
            if (not interaction.user.guild_permissions.administrator
                    and self.service.page_times.get(self.guild_id, 0) > now):
                await interaction.followup.send('Espera un momento antes de cambiar de página.', ephemeral=True)
                return
            self.service.page_times[self.guild_id] = now + 1
            config = self.service.config[str(self.guild_id)]
            config['page'] = config.get('page', 0) + delta
            updated = await self.service.safe_sync(self.guild_id)
        await interaction.followup.send('Página actualizada.' if updated else 'No pude actualizar el panel.', ephemeral=True)

    @discord.ui.button(label='Anterior', style=discord.ButtonStyle.secondary, custom_id='whitelist:previous')
    async def previous(self, interaction, button):
        await self.turn_page(interaction, -1)

    @discord.ui.button(label='Siguiente', style=discord.ButtonStyle.secondary, custom_id='whitelist:next')
    async def next(self, interaction, button):
        await self.turn_page(interaction, 1)


class NicknameModal(discord.ui.Modal):
    def __init__(self, service, interaction):
        super().__init__(title='Registrar nickname de Minecraft', timeout=180)
        self.service, self.guild_id, self.user_id = service, interaction.guild_id, interaction.user.id
        self.channel_id, self.message_id = interaction.channel_id, interaction.message.id
        self.deadline, self.submitted = time.monotonic() + 180, False
        self.nickname = discord.ui.TextInput(label='Nickname de Minecraft Java', min_length=3, max_length=16,
                                             placeholder='Escríbelo respetando mayúsculas y minúsculas')
        self.add_item(self.nickname)

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True)
        async with self.service.lock:
            config = self.service.config.get(str(self.guild_id), {})
            if (interaction.guild_id != self.guild_id or interaction.user.id != self.user_id
                    or not isinstance(interaction.user, discord.Member) or self.submitted
                    or interaction.user.guild.id != self.guild_id
                    or time.monotonic() > self.deadline or not config.get('enabled')
                    or config.get('channel_id') != self.channel_id or config.get('message_id') != self.message_id
                    or interaction.channel_id != self.channel_id):
                await interaction.followup.send('El formulario venció o ya no está activo.', ephemeral=True)
                return
            try:
                self.service.change(self.guild_id, self.user_id, str(self.nickname.value))
            except ValueError as error:
                await interaction.followup.send(str(error), ephemeral=True)
                return
            self.submitted = True
            config['page'] = (len(self.service.members[str(self.guild_id)]) - 1) // PAGE_SIZE
            synced = await self.service.safe_sync(self.guild_id)
        result = 'Nickname registrado en la whitelist.' if synced else 'Nickname guardado. El staff debe usar /whitelist sincronizar para actualizar el panel.'
        await interaction.followup.send(result, ephemeral=True)

    async def on_error(self, interaction, error):
        logging.error('Whitelist form failed', exc_info=(type(error), error, error.__traceback__))
        if interaction.response.is_done():
            await interaction.followup.send('No pude completar el registro. Contacta al staff.', ephemeral=True)
        else:
            await interaction.response.send_message('No pude completar el registro. Contacta al staff.', ephemeral=True)


def setup(bot):
    service = WhitelistService(bot)
    bot.whitelist = service
    service.restore()
    bot.add_listener(service.on_ready, 'on_ready')
    group = app_commands.Group(name='whitelist', description='Administración de la lista de nicknames',
                               default_permissions=discord.Permissions(administrator=True))

    @group.command(name='configurar', description='Publica el panel permanente de whitelist en un canal')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def configure(interaction: discord.Interaction, canal: discord.TextChannel):
        if canal.guild.id != interaction.guild_id:
            await interaction.response.send_message('Selecciona un canal de este servidor.', ephemeral=True)
            return
        permissions = canal.permissions_for(interaction.guild.me)
        if not (permissions.view_channel and permissions.send_messages and permissions.embed_links and permissions.read_message_history):
            await interaction.response.send_message('El bot necesita Ver canal, Enviar mensajes, Insertar enlaces y Leer historial.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        async with service.lock:
            config = service.config.setdefault(str(interaction.guild_id), {})
            config.update(enabled=True, channel_id=canal.id)
            write_json(CONFIG_FILE, service.config)
            synced = await service.safe_sync(interaction.guild_id)
        await interaction.followup.send('Panel de whitelist publicado.' if synced else 'Configuración guardada. Reintenta con /whitelist sincronizar.', ephemeral=True)

    async def modify(interaction, usuario, nickname, editing):
        await interaction.response.defer(ephemeral=True)
        async with service.lock:
            if usuario.guild.id != interaction.guild_id:
                await interaction.followup.send('Selecciona un miembro de este servidor.', ephemeral=True)
                return
            if not service.config.get(str(interaction.guild_id), {}).get('enabled'):
                await interaction.followup.send('Primero usa /whitelist configurar.', ephemeral=True)
                return
            try:
                service.change(interaction.guild_id, usuario.id, nickname, editing, interaction.user.id)
            except ValueError as error:
                await interaction.followup.send(str(error), ephemeral=True)
                return
            synced = await service.safe_sync(interaction.guild_id)
        await interaction.followup.send('Nickname actualizado.' if synced else 'Guardado. Usa /whitelist sincronizar para actualizar el panel.', ephemeral=True)

    @group.command(name='agregar', description='Registra un nickname para un usuario de Discord')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def add(interaction: discord.Interaction, usuario: discord.Member, nickname: str):
        await modify(interaction, usuario, nickname, False)

    @group.command(name='editar', description='Cambia el nickname registrado de un usuario')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def edit(interaction: discord.Interaction, usuario: discord.Member, nickname: str):
        await modify(interaction, usuario, nickname, True)

    @group.command(name='eliminar', description='Elimina el registro de un usuario')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def remove(interaction: discord.Interaction, usuario: discord.User):
        await interaction.response.defer(ephemeral=True)
        async with service.lock:
            members = service.members.get(str(interaction.guild_id), {})
            if str(usuario.id) not in members:
                await interaction.followup.send('Ese usuario no tiene un registro.', ephemeral=True)
                return
            del members[str(usuario.id)]
            write_json(STATE_FILE, service.members)
            synced = await service.safe_sync(interaction.guild_id)
        await interaction.followup.send('Registro eliminado.' if synced else 'Registro eliminado. Usa /whitelist sincronizar para actualizar el panel.', ephemeral=True)

    @group.command(name='sincronizar', description='Actualiza o recupera el panel sin cambiar los registros')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def synchronize(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with service.lock:
            if not service.config.get(str(interaction.guild_id), {}).get('enabled'):
                await interaction.followup.send('Primero usa /whitelist configurar.', ephemeral=True)
                return
            synced = await service.safe_sync(interaction.guild_id)
        await interaction.followup.send('Panel actualizado.' if synced else 'No pude actualizar el panel. Revisa los permisos del bot.', ephemeral=True)

    async def export(interaction, lowercase):
        await interaction.response.defer(ephemeral=True)
        async with service.lock:
            text = service.export(interaction.guild_id, lowercase)
        if not text:
            await interaction.followup.send('La whitelist está vacía.', ephemeral=True)
            return
        filename = 'whitelist-minusculas.txt' if lowercase else 'whitelist-original.txt'
        file = discord.File(io.BytesIO(text.encode('utf-8')), filename=filename)
        await interaction.followup.send(file=file, ephemeral=True)

    @group.command(name='exportar', description='Descarga todos los nicknames tal como fueron escritos, uno por línea')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def export_original(interaction: discord.Interaction):
        await export(interaction, False)

    @group.command(name='exportar_minusculas', description='Descarga todos los nicknames en minúsculas, uno por línea')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def export_lowercase(interaction: discord.Interaction):
        await export(interaction, True)

    bot.tree.add_command(group)
