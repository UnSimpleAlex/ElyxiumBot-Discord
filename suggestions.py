"""Guild suggestions, persistent voting, and role-restricted staff review."""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field

import discord
from discord import app_commands

from common import ResponsiveView, read_json, write_json


CONFIG_FILE = 'data/suggestions_config.json'
STATE_FILE = 'data/suggestions.json'
EMOJI = {
    'form': '<:1366121378494812271:1555793470545862756>',
    'suggestion': '<:1418788298029273125:1552144675413172284>',
    'up': '<:1423392237466681355:1552194563832291368>',
    'down': '<:1002617024486322356:1555793553114931280>',
    'accept': '<:975769597309517904:1555793557246189639>',
    'deny': '<:1418788295361429564:1552144656786002041>',
    'delete': '<:1423561224339193916:1555793534672568392>',
    'staff': '<:892934806625726514:1555815286085652531>',
}
COLORS = {'pending': 0xF1C40F, 'accepted': 0x2ECC71, 'denied': 0xE74C3C, 'deleted': 0x95A5A6}
STATUS = {'pending': 'PENDIENTE DE REVISIÓN', 'accepted': 'ACEPTADA', 'denied': 'DENEGADA', 'deleted': 'ELIMINADA'}


@dataclass
class FormRequest:
    guild_id: int
    author_id: int
    channel_id: int
    deadline: float = field(default_factory=lambda: time.monotonic() + 180)
    submitted: bool = False


def render_panel():
    embed = discord.Embed(
        title='𝙱𝚄𝚉𝙾́𝙽 𝙳𝙴 𝚂𝚄𝙶𝙴𝚁𝙴𝙽𝙲𝙸𝙰𝚂',
        description=f"{EMOJI['form']} **TU IDEA PUEDE MEJORAR ELYXIUM STUDIO**\n\n"
                    'Comparte tu propuesta y explica qué aportaría a la comunidad.\n\n'
                    f"{EMOJI['suggestion']} Presiona **SUGERIR** para completar el formulario. "
                    'Tu sugerencia se publicará aquí para que la comunidad vote y el staff la revise.',
        color=0x26B99A,
    )
    embed.set_footer(text='Elyxium Studio · Ideas, comunidad y creatividad')
    return embed


def count_votes(record):
    votes = record.get('votes', {}).values()
    return sum(v == 1 for v in votes), sum(v == -1 for v in record.get('votes', {}).values())


def render(record, staff=False):
    up, down = count_votes(record)
    embed = discord.Embed(
        title='𝚂𝚄𝙶𝙴𝚁𝙴𝙽𝙲𝙸𝙰 · ' + STATUS[record['status']],
        description=f"{EMOJI['suggestion']} **{discord.utils.escape_markdown(record['title'])}**\n\n{record['description']}",
        color=COLORS[record['status']],
    )
    embed.add_field(name='AUTOR', value=f"<@{record['author_id']}>", inline=True)
    embed.add_field(name='VOTOS', value=f"{EMOJI['up']} **{up}** a favor  ·  {EMOJI['down']} **{down}** en contra", inline=True)
    if record.get('reviewer_id'):
        embed.add_field(name='REVISIÓN', value=f"{EMOJI['staff']} <@{record['reviewer_id']}>\n{record.get('reason') or 'Sin observaciones.'}", inline=False)
    if staff and record.get('public_message_id'):
        embed.add_field(name='MENSAJE ORIGINAL', value=f"[Ver sugerencia](https://discord.com/channels/{record['guild_id']}/{record['public_channel_id']}/{record['public_message_id']})", inline=False)
    embed.set_footer(text=f"Elyxium Studio · ID: {record['id']} · Un voto por persona")
    return embed


class SuggestionService:
    def __init__(self, bot):
        self.bot = bot
        self.config = read_json(CONFIG_FILE, {})
        self.records = read_json(STATE_FILE, {})
        self.requests = {}
        self.panel_views = {}
        self.lock = asyncio.Lock()

    def save(self):
        write_json(STATE_FILE, self.records)

    def reviewer(self, user, guild_id):
        config = self.config.get(str(guild_id), {})
        return isinstance(user, discord.Member) and user.guild.id == guild_id and any(
            role.id == config.get('review_role_id') for role in user.roles
        )

    def restore(self):
        for guild_id, config in self.config.items():
            if config.get('enabled') and config.get('panel_message_id'):
                view = PanelView(self, int(guild_id))
                self.panel_views[int(guild_id)] = view
                self.bot.add_view(view, message_id=config['panel_message_id'])
        for record in self.records.values():
            if record['status'] == 'deleted':
                continue
            if record.get('public_message_id'):
                self.bot.add_view(VoteView(self, record['id']), message_id=record['public_message_id'])
            if record.get('staff_message_id'):
                self.bot.add_view(ReviewView(self, record['id']), message_id=record['staff_message_id'])

    async def channel(self, channel_id):
        return self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)

    async def move_panel(self, guild_id):
        config = self.config[str(guild_id)]
        if not config.get('enabled'):
            return
        channel = await self.channel(config['public_channel_id'])
        old_id = config.get('panel_message_id')
        old_channel = config.get('panel_channel_id', config['public_channel_id'])
        # Publish before removing the old panel so a failed send leaves a usable button.
        view = PanelView(self, guild_id)
        message = await channel.send(embed=render_panel(), view=view,
                                     allowed_mentions=discord.AllowedMentions.none())
        previous_view = self.panel_views.get(guild_id)
        if previous_view:
            previous_view.stop()
        self.panel_views[guild_id] = view
        config['panel_message_id'], config['panel_channel_id'] = message.id, channel.id
        if old_id:
            config.setdefault('obsolete_panels', []).append({'channel_id': old_channel, 'message_id': old_id})
        write_json(CONFIG_FILE, self.config)
        await self.clean_old_panels(config)

    async def clean_old_panels(self, config):
        remaining = []
        for old in config.get('obsolete_panels', []):
            try:
                channel = await self.channel(old['channel_id'])
                await channel.get_partial_message(old['message_id']).delete()
            except discord.NotFound:
                pass
            except discord.HTTPException:
                remaining.append(old)
                logging.exception('Could not remove old suggestion panel')
        config['obsolete_panels'] = remaining
        write_json(CONFIG_FILE, self.config)

    async def ensure_panels(self):
        async with self.lock:
            for guild_id, config in self.config.items():
                if not config.get('enabled'):
                    continue
                try:
                    await self.clean_old_panels(config)
                    if config.get('panel_message_id'):
                        channel = await self.channel(config['public_channel_id'])
                        try:
                            await channel.fetch_message(config['panel_message_id'])
                            continue
                        except discord.NotFound:
                            pass
                    await self.move_panel(int(guild_id))
                except discord.HTTPException:
                    logging.exception('Could not restore suggestion panel in guild %s', guild_id)

    async def sync(self, record):
        for staff, prefix in ((False, 'public'), (True, 'staff')):
            channel = await self.channel(record[f'{prefix}_channel_id'])
            view = ReviewView(self, record['id']) if staff else VoteView(self, record['id'])
            message_id = record.get(f'{prefix}_message_id')
            if message_id:
                try:
                    await channel.get_partial_message(message_id).edit(embed=render(record, staff), view=view)
                    continue
                except discord.NotFound:
                    pass
            message = await channel.send(embed=render(record, staff), view=view, allowed_mentions=discord.AllowedMentions.none())
            record[f'{prefix}_message_id'] = message.id
            self.save()
            if not staff:
                try:
                    await self.move_panel(record['guild_id'])
                except discord.HTTPException:
                    logging.exception('Suggestion published, but panel could not be moved; use /sugerencias panel')

    async def publish(self, interaction, request, title, description):
        await interaction.response.defer(ephemeral=True, thinking=True)
        key = (request.guild_id, request.author_id)
        async with self.lock:
            config = self.config.get(str(interaction.guild_id), {})
            if (self.requests.get(key) is not request or request.submitted
                    or time.monotonic() >= request.deadline or interaction.user.id != key[1]
                    or interaction.guild_id != key[0] or not config.get('enabled')
                    or config.get('public_channel_id') != request.channel_id):
                await interaction.followup.send('El formulario venció o ya fue enviado. Presiona Sugerir para abrir otro.', ephemeral=True)
                return
            if not title.strip() or not description.strip():
                await interaction.followup.send('El título y la descripción no pueden estar vacíos.', ephemeral=True)
                return
            recent = [r for r in self.records.values() if r['author_id'] == key[1] and r['guild_id'] == key[0] and time.time() - r['created_at'] < 180]
            if recent:
                await interaction.followup.send('Espera tres minutos entre sugerencias.', ephemeral=True)
                return
            if len(self.records) >= 10000:
                await interaction.followup.send('El sistema alcanzó su límite de registros. Contacta al staff.', ephemeral=True)
                return
            request.submitted = True
            record = {
                'id': uuid.uuid4().hex[:16], 'guild_id': key[0], 'author_id': key[1],
                'title': title.strip(), 'description': description.strip(), 'created_at': time.time(),
                'status': 'pending', 'votes': {}, 'public_channel_id': config['public_channel_id'],
                'staff_channel_id': config['staff_channel_id'],
            }
            self.records[record['id']] = record
            self.save()
            try:
                await self.sync(record)
                result = f"Sugerencia publicada. ID: `{record['id']}`. El staff recibió una copia para revisarla."
            except discord.HTTPException:
                logging.exception('Suggestion delivery incomplete: %s', record['id'])
                result = f"Sugerencia guardada con ID `{record['id']}`, pero no pude enviar todos los mensajes. El staff puede usar /sugerencias sincronizar."
        await interaction.followup.send(result, ephemeral=True)

    async def vote(self, interaction, suggestion_id, choice):
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.lock:
            record = self.records.get(suggestion_id)
            if not record or record['guild_id'] != interaction.guild_id or interaction.message.id != record.get('public_message_id') or record['status'] != 'pending' or choice not in (1, -1):
                await interaction.followup.send('Esta sugerencia no está disponible para votar.', ephemeral=True)
                return
            user_id = str(interaction.user.id)
            last_vote = record.setdefault('vote_times', {}).get(user_id, 0)
            if time.time() - last_vote < 5:
                await interaction.followup.send('Espera cinco segundos antes de cambiar tu voto.', ephemeral=True)
                return
            if len(record['votes']) >= 20000 and user_id not in record['votes']:
                await interaction.followup.send('Se alcanzó el límite de votos.', ephemeral=True)
                return
            previous = record['votes'].get(user_id)
            record['vote_times'][user_id] = time.time()
            if previous == choice:
                del record['votes'][user_id]
                result = 'Retiraste tu voto.'
            else:
                record['votes'][user_id] = choice
                result = 'Voto registrado.' if previous is None else 'Cambiaste tu voto.'
            self.save()
            try:
                await self.sync(record)
            except discord.HTTPException:
                logging.exception('Vote saved; message update failed')
                result += ' El contador se guardó, pero el mensaje no pudo actualizarse todavía.'
        await interaction.followup.send(result, ephemeral=True)

    async def review(self, interaction, suggestion_id, action, reason):
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.lock:
            record = self.records.get(suggestion_id)
            if (action not in ('accepted', 'denied', 'deleted') or not record or record['guild_id'] != interaction.guild_id
                    or not self.reviewer(interaction.user, interaction.guild_id)
                    or interaction.channel_id != record['staff_channel_id']):
                await interaction.followup.send('Solo el rol de revisión puede realizar esta acción desde el canal del staff.', ephemeral=True)
                return
            if record['status'] == 'deleted' or (action != 'deleted' and record['status'] != 'pending'):
                await interaction.followup.send('La sugerencia ya fue revisada.', ephemeral=True)
                return
            if action in ('denied', 'deleted') and not reason.strip():
                await interaction.followup.send('Escribe un motivo para denegar o eliminar la sugerencia.', ephemeral=True)
                return
            if action == 'deleted':
                # Delete Discord messages first; retain IDs for retry if an API call fails.
                for prefix in ('public', 'staff'):
                    message_id = record.get(f'{prefix}_message_id')
                    if message_id:
                        channel = await self.channel(record[f'{prefix}_channel_id'])
                        try:
                            await channel.get_partial_message(message_id).delete()
                        except discord.NotFound:
                            pass
            record.update(status=action, reviewer_id=interaction.user.id, reason=reason.strip()[:500], reviewed_at=time.time())
            self.save()
            if action != 'deleted':
                try:
                    await self.sync(record)
                except discord.HTTPException:
                    logging.exception('Review saved; message update failed')
                    await interaction.followup.send('Decisión guardada. No pude actualizar los mensajes; usa /sugerencias sincronizar.', ephemeral=True)
                    return
        await interaction.followup.send('Sugerencia ' + STATUS[action].lower() + '.', ephemeral=True)


class PanelView(ResponsiveView):
    def __init__(self, service, guild_id):
        super().__init__(timeout=None)
        self.service, self.guild_id = service, guild_id
        self.suggest.custom_id = f'suggest_panel_{guild_id}'
        self.suggest.emoji = discord.PartialEmoji.from_str(EMOJI['form'])

    @discord.ui.button(label='Sugerir', style=discord.ButtonStyle.primary)
    async def suggest(self, interaction, button):
        config = self.service.config.get(str(self.guild_id), {})
        if (not config.get('enabled') or interaction.guild_id != self.guild_id
                or interaction.channel_id != config.get('public_channel_id')
                or interaction.message.id != config.get('panel_message_id')):
            await interaction.response.send_message('Este panel ya no está activo. Usa el panel más reciente del canal.', ephemeral=True)
            return
        now = time.monotonic()
        self.service.requests = {key: value for key, value in self.service.requests.items()
                                 if value.deadline > now and not value.submitted}
        key = (self.guild_id, interaction.user.id)
        request = self.service.requests.get(key)
        if request is None:
            if len(self.service.requests) >= 500:
                await interaction.response.send_message('Hay muchos formularios abiertos. Intenta de nuevo en unos minutos.', ephemeral=True)
                return
            request = FormRequest(self.guild_id, interaction.user.id, interaction.channel_id)
            self.service.requests[key] = request
        await interaction.response.send_modal(SuggestionModal(self.service, request))


class SuggestionModal(discord.ui.Modal):
    def __init__(self, service, request):
        super().__init__(title='Nueva sugerencia', timeout=180)
        self.request = request
        self.service = service
        self.subject = discord.ui.TextInput(label='Título de tu idea', max_length=150)
        self.body = discord.ui.TextInput(label='¿Qué propones y qué mejora?', style=discord.TextStyle.paragraph,
                                         max_length=2400)
        self.add_item(self.subject)
        self.add_item(self.body)

    async def on_submit(self, interaction):
        await self.service.publish(interaction, self.request, self.subject.value, self.body.value)

    async def on_error(self, interaction, error):
        await ResponsiveView().on_error(interaction, error, self)


class VoteView(ResponsiveView):
    def __init__(self, service, suggestion_id):
        super().__init__(timeout=None)
        self.service, self.suggestion_id = service, suggestion_id
        record = service.records[suggestion_id]
        up, down = count_votes(record)
        self.positive.custom_id = f'suggest_vote_{suggestion_id}_up'
        self.negative.custom_id = f'suggest_vote_{suggestion_id}_down'
        self.positive.label, self.negative.label = f'A favor · {up}', f'En contra · {down}'
        self.positive.emoji = discord.PartialEmoji.from_str(EMOJI['up'])
        self.negative.emoji = discord.PartialEmoji.from_str(EMOJI['down'])
        for child in self.children:
            child.disabled = record['status'] != 'pending'

    @discord.ui.button(label='A favor', style=discord.ButtonStyle.success)
    async def positive(self, interaction, button):
        await self.service.vote(interaction, self.suggestion_id, 1)

    @discord.ui.button(label='En contra', style=discord.ButtonStyle.danger)
    async def negative(self, interaction, button):
        await self.service.vote(interaction, self.suggestion_id, -1)


class ReviewView(ResponsiveView):
    def __init__(self, service, suggestion_id):
        super().__init__(timeout=None)
        self.service, self.suggestion_id = service, suggestion_id
        for child, action, emoji in ((self.accept, 'accepted', 'accept'), (self.deny, 'denied', 'deny'), (self.delete, 'deleted', 'delete')):
            child.custom_id = f'suggest_review_{suggestion_id}_{action}'
            child.emoji = discord.PartialEmoji.from_str(EMOJI[emoji])
            child.disabled = service.records[suggestion_id]['status'] != 'pending' and action != 'deleted'

    async def open_review(self, interaction, action):
        record = self.service.records[self.suggestion_id]
        if (not self.service.reviewer(interaction.user, interaction.guild_id)
                or interaction.channel_id != record['staff_channel_id']
                or interaction.message.id != record.get('staff_message_id')):
            await interaction.response.send_message('Solo el rol configurado puede revisar sugerencias desde su mensaje en el canal del staff.', ephemeral=True)
            return
        await interaction.response.send_modal(ReviewModal(self, action))

    @discord.ui.button(label='Aceptar', style=discord.ButtonStyle.success)
    async def accept(self, interaction, button):
        await self.open_review(interaction, 'accepted')

    @discord.ui.button(label='Denegar', style=discord.ButtonStyle.danger)
    async def deny(self, interaction, button):
        await self.open_review(interaction, 'denied')

    @discord.ui.button(label='Eliminar', style=discord.ButtonStyle.secondary)
    async def delete(self, interaction, button):
        await self.open_review(interaction, 'deleted')


class ReviewModal(discord.ui.Modal):
    def __init__(self, view, action):
        super().__init__(title={'accepted': 'Aceptar sugerencia', 'denied': 'Denegar sugerencia', 'deleted': 'Confirmar eliminación'}[action], timeout=180)
        self.view, self.action = view, action
        self.reason = discord.ui.TextInput(label='Motivo o comentario', style=discord.TextStyle.paragraph,
                                           max_length=500, required=action != 'accepted')
        self.add_item(self.reason)

    async def on_submit(self, interaction):
        await self.view.service.review(interaction, self.view.suggestion_id, self.action, self.reason.value)

    async def on_error(self, interaction, error):
        await ResponsiveView().on_error(interaction, error, self)


def setup(bot):
    service = SuggestionService(bot)
    bot.suggestions = service
    service.restore()
    bot.add_listener(service.ensure_panels, 'on_ready')
    group = app_commands.Group(name='sugerencias', description='Configuración y revisión de sugerencias')

    @group.command(name='configurar', description='Configura el canal público, el canal del staff y el rol de revisión')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def configure(interaction: discord.Interaction, canal_sugerencias: discord.TextChannel,
                        canal_staff: discord.TextChannel, rol_revision: discord.Role):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if canal_sugerencias.guild.id != interaction.guild_id or canal_staff.guild.id != interaction.guild_id or rol_revision.guild.id != interaction.guild_id or rol_revision.is_default() or canal_staff.id == canal_sugerencias.id:
            await interaction.followup.send('Selecciona dos canales diferentes de este servidor y un rol distinto de @everyone.', ephemeral=True)
            return
        for channel in (canal_sugerencias, canal_staff):
            permissions = channel.permissions_for(interaction.guild.me)
            if not all((permissions.view_channel, permissions.send_messages, permissions.embed_links, permissions.read_message_history)):
                await interaction.followup.send('El bot necesita Ver canal, Enviar mensajes, Insertar enlaces y Leer historial en ambos canales.', ephemeral=True)
                return
        if canal_staff.permissions_for(interaction.guild.default_role).view_channel:
            await interaction.followup.send('El canal del staff debe ser privado: deniega Ver canal a @everyone.', ephemeral=True)
            return
        reviewer_access = canal_staff.permissions_for(rol_revision)
        if not reviewer_access.view_channel or not reviewer_access.read_message_history:
            await interaction.followup.send('El rol de revisión necesita acceso al canal del staff y su historial.', ephemeral=True)
            return
        async with service.lock:
            old = service.config.get(str(interaction.guild_id), {})
            service.config[str(interaction.guild_id)] = {**old, 'enabled': True, 'public_channel_id': canal_sugerencias.id,
                                                        'staff_channel_id': canal_staff.id, 'review_role_id': rol_revision.id}
            write_json(CONFIG_FILE, service.config)
            await service.move_panel(interaction.guild_id)
        await interaction.followup.send(f'Sistema activado en {canal_sugerencias.mention}. Revisión: {canal_staff.mention}. Rol autorizado: {rol_revision.mention}.', ephemeral=True)

    @group.command(name='sincronizar', description='Reintenta publicar o actualizar los mensajes de una sugerencia')
    @app_commands.guild_only()
    async def synchronize(interaction: discord.Interaction, sugerencia_id: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not service.reviewer(interaction.user, interaction.guild_id):
            await interaction.followup.send('Solo el rol de revisión puede sincronizar sugerencias.', ephemeral=True)
            return
        async with service.lock:
            record = service.records.get(sugerencia_id)
            if not record or record['guild_id'] != interaction.guild_id or record['status'] == 'deleted':
                await interaction.followup.send('No existe una sugerencia disponible con ese ID en este servidor.', ephemeral=True)
                return
            await service.sync(record)
        await interaction.followup.send('Mensajes sincronizados.', ephemeral=True)

    @group.command(name='desactivar', description='Detiene los nuevos formularios; conserva votos y sugerencias')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def disable(interaction: discord.Interaction):
        config = service.config.get(str(interaction.guild_id))
        if config:
            config['enabled'] = False
            write_json(CONFIG_FILE, service.config)
        await interaction.response.send_message('Nuevos formularios desactivados. Las sugerencias existentes se conservan.', ephemeral=True)

    @group.command(name='panel', description='Publica o mueve el panel con el botón Sugerir al final del canal')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def panel(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        config = service.config.get(str(interaction.guild_id), {})
        if not config.get('enabled'):
            await interaction.followup.send('Primero configura el sistema con /sugerencias configurar.', ephemeral=True)
            return
        async with service.lock:
            await service.move_panel(interaction.guild_id)
        await interaction.followup.send('Panel de sugerencias publicado al final del canal.', ephemeral=True)

    bot.tree.add_command(group)
