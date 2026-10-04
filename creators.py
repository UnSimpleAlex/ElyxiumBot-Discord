"""Role-scoped creator announcements with URL validation and persistent cooldowns."""
import asyncio
import logging
import re
import time
from urllib.parse import parse_qs, urlsplit, urlunsplit

import discord
from discord import app_commands
from discord.ext import commands

from common import ResponsiveView, SERVER_EMOJIS, StudioEmbed, read_json, write_json


CONFIG_FILE = 'data/creators_config.json'
STATE_FILE = 'data/creators_announcements.json'
PLATFORM_EMOJIS = {
    'YouTube': SERVER_EMOJIS['youtube'],
    'Kick': SERVER_EMOJIS['kick'],
    'TikTok': SERVER_EMOJIS['tiktok'],
    'Twitch': SERVER_EMOJIS['twitch'],
}
CREATOR_BANNER = 'https://res.cloudinary.com/y08rn1qr/image/upload/v1791071381/53eebc41-a7fd-4661-bbf6-c34b057f6a6d.png'
CREATOR_COLOR = 0x9B59B6


def validate_link(value, kind):
    """Validate canonical platform hosts and routes without fetching user URLs."""
    if kind not in ('directo', 'video'):
        raise ValueError('Tipo de anuncio inválido.')
    value = value.strip()
    if len(value) > 500 or re.search(r'[\s\\<>\x00-\x1f()]', value):
        raise ValueError('El enlace contiene caracteres no permitidos.')
    try:
        url = urlsplit(value)
        if url.scheme != 'https' or url.username or url.password or url.port is not None or url.fragment:
            raise ValueError()
        host, path = (url.hostname or '').lower(), url.path.rstrip('/')
        query = parse_qs(url.query)
    except ValueError:
        raise ValueError('Usa un enlace HTTPS completo, sin credenciales, puerto ni fragmento.') from None
    platform, valid = None, False
    if host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'):
        platform = 'YouTube'
        video_id = r'[A-Za-z0-9_-]{11}'
        valid = bool((host == 'youtu.be' and re.fullmatch('/' + video_id, path)) or
                     (host != 'youtu.be' and path == '/watch' and len(query.get('v', [])) == 1
                      and re.fullmatch(video_id, query['v'][0])) or
                     (host != 'youtu.be' and re.fullmatch(r'/(?:live|shorts)/' + video_id, path)))
        if kind == 'directo' and host != 'youtu.be':
            valid = valid or bool(re.fullmatch(r'/(?:@[A-Za-z0-9_.-]+|channel/[A-Za-z0-9_-]+)/live', path))
    elif host in ('twitch.tv', 'www.twitch.tv', 'clips.twitch.tv'):
        platform = 'Twitch'
        if kind == 'directo':
            valid = host != 'clips.twitch.tv' and bool(re.fullmatch(r'/[A-Za-z0-9_]{1,25}', path))
            valid = valid and path.lower() not in ('/videos', '/directory', '/downloads', '/settings', '/search', '/login', '/signup', '/subscriptions', '/inventory', '/wallet')
        else:
            valid = bool(re.fullmatch(r'/videos/\d+|/[A-Za-z0-9_]+/clip/[A-Za-z0-9_-]+', path))
            if host == 'clips.twitch.tv':
                valid = bool(re.fullmatch(r'/[A-Za-z0-9_-]+', path))
    elif host in ('kick.com', 'www.kick.com'):
        platform = 'Kick'
        if kind == 'directo':
            valid = bool(re.fullmatch(r'/[A-Za-z0-9_-]+', path)) and not query.get('clip')
            valid = valid and path.lower() not in ('/categories', '/search', '/settings', '/video', '/login', '/register', '/browse', '/terms', '/privacy')
        else:
            valid = bool(re.fullmatch(r'/(?:[A-Za-z0-9_-]+/videos|video)/[A-Za-z0-9_-]+', path) or
                         (re.fullmatch(r'/[A-Za-z0-9_-]+', path) and len(query.get('clip', [])) == 1
                          and re.fullmatch(r'[A-Za-z0-9_-]+', query['clip'][0])))
    elif host in ('tiktok.com', 'www.tiktok.com', 'm.tiktok.com'):
        platform = 'TikTok'
        route = r'/@[A-Za-z0-9_.]+/live' if kind == 'directo' else r'/@[A-Za-z0-9_.]+/video/\d+'
        valid = bool(re.fullmatch(route, path))
    if not valid:
        raise ValueError('Usa el enlace del directo o video de YouTube, Twitch, Kick o TikTok; no enlaces acortados de TikTok ni enlaces de perfil para videos.')
    return platform, urlunsplit(('https', host, url.path, url.query, ''))


def render_panel():
    embed = StudioEmbed(title='𝙰𝙽𝚄𝙽𝙲𝙸𝙾𝚂 𝙳𝙴 𝙲𝚁𝙴𝙰𝙳𝙾𝚁𝙴𝚂',
                        description=f"{SERVER_EMOJIS['announcement']} **COMPARTE TU CONTENIDO CON LA COMUNIDAD**\n\n"
                                    'Selecciona **DIRECTO** o **VIDEO** y comparte el enlace de tu publicación.',
                        color=CREATOR_COLOR)
    embed.add_field(name='PLATAFORMAS', value='  ·  '.join(f'{emoji} {name}' for name, emoji in PLATFORM_EMOJIS.items()), inline=False)
    embed.set_image(url=CREATOR_BANNER)
    return embed


def render_announcement(user, platform, url, kind, headline='', summary=''):
    label = '𝙴𝙻 𝙳𝙸𝚁𝙴𝙲𝚃𝙾 𝙲𝙾𝙼𝙸𝙴𝙽𝚉𝙰' if kind == 'directo' else '𝙽𝚄𝙴𝚅𝙾 𝚅𝙸𝙳𝙴𝙾 𝙿𝙰𝚁𝙰 𝚃𝙸'
    introduction = (f"{SERVER_EMOJIS['announcement']} {user.mention} te invita a su **DIRECTO EN {platform.upper()}**." if kind == 'directo'
                    else f"{SERVER_EMOJIS['document']} {user.mention} tiene un **NUEVO VIDEO EN {platform.upper()}** para la comunidad.")
    summary = summary or ('Entra, saluda en el chat y vive la experiencia junto a la comunidad de Elyxium Studio.' if kind == 'directo'
                          else 'Descubre lo nuevo, deja tu opinión y apoya el contenido de nuestros creadores.')
    closing = (f"{SERVER_EMOJIS['heart']} **NOS VEMOS EN EL CHAT**" if kind == 'directo'
               else f"{SERVER_EMOJIS['badge']} **DALE PLAY Y SÉ PARTE**")
    embed = StudioEmbed(title=f'{PLATFORM_EMOJIS[platform]} {headline or label}',
                        description=f"{introduction}\n\n{SERVER_EMOJIS['pencil']} {discord.utils.escape_markdown(summary)}\n\n{closing}",
                        color=CREATOR_COLOR, timestamp=discord.utils.utcnow())
    avatar = getattr(getattr(user, 'display_avatar', None), 'url', None)
    name = getattr(user, 'display_name', None)
    author = {'name': name if isinstance(name, str) else 'Creador de la comunidad'}
    if isinstance(avatar, str) and avatar.startswith('https://'):
        author['icon_url'] = avatar
        embed.set_thumbnail(url=avatar)
    embed.set_author(**author)
    embed.set_image(url=CREATOR_BANNER)
    return embed


def announcement_link_view(platform, url, kind):
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(label='Ver directo' if kind == 'directo' else 'Ver video',
                                   style=discord.ButtonStyle.link, url=url,
                                   emoji=discord.PartialEmoji.from_str(PLATFORM_EMOJIS[platform])))
    return view


def creator_command_cooldown(message):
    if message.guild and message.author.guild_permissions.administrator:
        return None
    return commands.Cooldown(1, 10)


class CreatorService:
    def __init__(self, bot):
        self.bot = bot
        self.config = read_json(CONFIG_FILE, {})
        self.announcements = read_json(STATE_FILE, {})
        self.lock = asyncio.Lock()
        self.panel_cooldowns = {}

    def authorized(self, user, guild_id, channel_id):
        config = self.config.get(str(guild_id), {})
        if not config.get('enabled') or not isinstance(user, discord.Member) or user.guild.id != guild_id:
            return False
        return user.guild_permissions.administrator or (channel_id == config['channel_id'] and any(
            role.id in config['role_ids'] for role in user.roles))

    async def panel(self, user, guild_id, channel):
        if not self.authorized(user, guild_id, channel.id):
            return 'Necesitas uno de los roles de creador y usar el canal configurado. Los administradores también tienen acceso.'
        async with self.lock:
            now = time.monotonic()
            self.panel_cooldowns = {key: deadline for key, deadline in self.panel_cooldowns.items() if deadline > now}
            administrator = user.guild_permissions.administrator
            if not administrator and guild_id in self.panel_cooldowns:
                return 'Espera diez segundos antes de solicitar otro panel.'
            if not administrator:
                self.panel_cooldowns[guild_id] = now + 10
            await channel.send(embed=render_panel(), view=CreatorView(self, user.id, guild_id, channel.id),
                               delete_after=180, allowed_mentions=discord.AllowedMentions.none())
        return 'Panel de creadores publicado.'

    async def publish(self, interaction, modal):
        await interaction.response.defer(ephemeral=True)
        async with self.lock:
            if (interaction.user.id != modal.author_id or interaction.guild_id != modal.guild_id
                    or interaction.channel_id != modal.channel_id or time.monotonic() > modal.deadline
                    or not self.authorized(interaction.user, interaction.guild_id, interaction.channel_id)):
                await interaction.followup.send('El formulario venció o ya no tienes acceso.', ephemeral=True)
                return
            if modal.submitted:
                await interaction.followup.send('Este formulario ya fue enviado.', ephemeral=True)
                return
            try:
                platform, url = validate_link(str(modal.link.value), modal.kind)
            except ValueError as error:
                await interaction.followup.send(str(error), ephemeral=True)
                return
            now = time.time()
            self.announcements = {key: record for key, record in self.announcements.items()
                                  if record.get('created_at', 0) > now - 86400}
            config = self.config[str(interaction.guild_id)]
            key = f'{interaction.guild_id}:{interaction.user.id}'
            if key not in self.announcements and len(self.announcements) >= 10000:
                await interaction.followup.send('Se alcanzó el límite temporal de anuncios. Intenta más tarde.', ephemeral=True)
                return
            previous = self.announcements.get(key, {})
            remaining = int(previous.get('created_at', 0) + config.get('cooldown', 300) - now)
            if remaining >= 0 and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send(f'Espera {remaining + 1} segundos antes de publicar otro anuncio.', ephemeral=True)
                return
            channel = self.bot.get_channel(config['channel_id']) or await self.bot.fetch_channel(config['channel_id'])
            headline = str(getattr(getattr(modal, 'headline', None), 'value', '') or '').strip()[:150]
            summary = str(getattr(getattr(modal, 'summary', None), 'value', '') or '').strip()[:600]
            try:
                message = await channel.send(embed=render_announcement(interaction.user, platform, url, modal.kind, headline, summary),
                                             view=announcement_link_view(platform, url, modal.kind),
                                             allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                logging.exception('Creator announcement could not be sent')
                await interaction.followup.send('No pude publicar el anuncio. Revisa los permisos del bot.', ephemeral=True)
                return
            modal.submitted = True
            self.announcements[key] = {'created_at': now, 'message_id': message.id, 'channel_id': channel.id,
                                       'platform': platform, 'kind': modal.kind, 'url': url,
                                       'headline': headline, 'summary': summary}
            write_json(STATE_FILE, self.announcements)
        await interaction.followup.send(f'Anuncio publicado en {channel.mention}.', ephemeral=True)


class CreatorView(ResponsiveView):
    def __init__(self, service, author_id, guild_id, channel_id):
        super().__init__(timeout=180)
        self.service, self.author_id, self.guild_id, self.channel_id = service, author_id, guild_id, channel_id
        self.deadline = time.monotonic() + 180
        self.live.emoji = discord.PartialEmoji.from_str(SERVER_EMOJIS['announcement'])
        self.video.emoji = discord.PartialEmoji.from_str(SERVER_EMOJIS['pencil'])

    async def open_form(self, interaction, kind):
        if (interaction.user.id != self.author_id or interaction.guild_id != self.guild_id
                or interaction.channel_id != self.channel_id or time.monotonic() > self.deadline
                or not self.service.authorized(interaction.user, self.guild_id, self.channel_id)):
            await interaction.response.send_message('Este panel venció, pertenece a otra persona o ya no tienes acceso.', ephemeral=True)
            return
        await interaction.response.send_modal(CreatorModal(self.service, self.author_id, self.guild_id, self.channel_id, kind))

    @discord.ui.button(label='Directo', style=discord.ButtonStyle.success)
    async def live(self, interaction, button):
        await self.open_form(interaction, 'directo')

    @discord.ui.button(label='Video', style=discord.ButtonStyle.primary)
    async def video(self, interaction, button):
        await self.open_form(interaction, 'video')


class CreatorModal(discord.ui.Modal):
    def __init__(self, service, author_id, guild_id, channel_id, kind):
        super().__init__(title='Compartir ' + kind, timeout=180)
        self.service, self.author_id, self.guild_id, self.channel_id, self.kind = service, author_id, guild_id, channel_id, kind
        self.deadline, self.submitted = time.monotonic() + 180, False
        self.link = discord.ui.TextInput(label='Enlace de tu ' + kind, placeholder='https://...', max_length=500)
        self.add_item(self.link)
        self.headline = discord.ui.TextInput(label='Título (opcional)', max_length=150, required=False)
        self.summary = discord.ui.TextInput(label='Descripción (opcional)', style=discord.TextStyle.paragraph,
                                           max_length=600, required=False)
        self.add_item(self.headline)
        self.add_item(self.summary)

    async def on_submit(self, interaction):
        await self.service.publish(interaction, self)

    async def on_error(self, interaction, error):
        logging.error('Creator form failed', exc_info=(type(error), error, error.__traceback__))
        if interaction.response.is_done():
            await interaction.followup.send('No pude completar el anuncio. Contacta al staff.', ephemeral=True)
        else:
            await interaction.response.send_message('No pude completar el anuncio. Contacta al staff.', ephemeral=True)


def setup(bot):
    service = CreatorService(bot)
    bot.creators = service

    @app_commands.guild_only()
    async def slash(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        result = await service.panel(interaction.user, interaction.guild_id, interaction.channel)
        await interaction.followup.send(result, ephemeral=True)

    for name in ('directo', 'video'):
        bot.tree.add_command(app_commands.Command(name=name, description='Publica el panel de anuncios para creadores', callback=slash))

    @bot.command(name='directo', aliases=['video'])
    @commands.dynamic_cooldown(creator_command_cooldown, commands.BucketType.member)
    async def prefix(ctx):
        if ctx.guild is None:
            await ctx.send('Este comando solo funciona en el servidor.')
            return
        result = await service.panel(ctx.author, ctx.guild.id, ctx.channel)
        if result != 'Panel de creadores publicado.':
            await ctx.send(result, delete_after=30)

    @prefix.error
    async def prefix_error(ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send('Espera diez segundos antes de solicitar otro panel.', delete_after=10)
        else:
            logging.error('Creator command failed', exc_info=(type(error), error, error.__traceback__))
            await ctx.send('No pude enviar el panel. Comprueba los permisos del bot.', delete_after=30)

    group = app_commands.Group(name='creadores', description='Configura los anuncios de directos y videos')

    @group.command(name='configurar', description='Selecciona canal y roles autorizados para anunciar contenido')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def configure(interaction: discord.Interaction, canal: discord.TextChannel,
                        rol_streamer: discord.Role, rol_yt: discord.Role,
                        espera_segundos: app_commands.Range[int, 60, 86400] = 300):
        if canal.guild.id != interaction.guild_id or any(role.guild.id != interaction.guild_id or role.is_default()
                                                        for role in (rol_streamer, rol_yt)):
            await interaction.response.send_message('Selecciona un canal y roles de este servidor, distintos de @everyone.', ephemeral=True)
            return
        permissions = canal.permissions_for(interaction.guild.me)
        if not (permissions.view_channel and permissions.send_messages and permissions.embed_links):
            await interaction.response.send_message('El bot necesita Ver canal, Enviar mensajes e Insertar enlaces.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        async with service.lock:
            service.config[str(interaction.guild_id)] = {'enabled': True, 'channel_id': canal.id,
                'role_ids': list({rol_streamer.id, rol_yt.id}), 'cooldown': espera_segundos}
            write_json(CONFIG_FILE, service.config)
        await interaction.followup.send(f'Anuncios activados en {canal.mention} para {rol_streamer.mention} y {rol_yt.mention}. Espera entre anuncios: {espera_segundos} segundos.', ephemeral=True)

    @group.command(name='desactivar', description='Desactiva anuncios conservando la configuración')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def disable(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        async with service.lock:
            config = service.config.get(str(interaction.guild_id))
            if config:
                config['enabled'] = False
                write_json(CONFIG_FILE, service.config)
        await interaction.followup.send('Anuncios de creadores desactivados.', ephemeral=True)

    bot.tree.add_command(group)
