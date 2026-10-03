import json
import logging
import os
import re
import sys
import unicodedata
from pathlib import Path

import discord
from discord import app_commands


DATA_DIR = Path("data")
BRAND_FOOTER = '© Elyxium Studio Copyright 2026'
BRAND_LOGO = 'https://res.cloudinary.com/y08rn1qr/image/upload/v1790138294/IsotipoSinFondo.png'
TICKET_BANNER = 'https://res.cloudinary.com/y08rn1qr/image/upload/v1791069402/11f5e871-f272-4896-bea5-9564d8b268d5.png'
VERIFICATION_BANNER = 'https://res.cloudinary.com/y08rn1qr/image/upload/v1791069538/5011a91b-0071-461f-aed7-7628c445bd4c.png'
SERVER_EMOJIS = {
    'document': '<:1418788298029273125:1552144675413172284>',
    'key': '<:1423423792872689755:1552181100187750430>',
    'shield': '<:892934806625726514:1555815286085652531>',
    'pencil': '<:1366121378494812271:1555793470545862756>',
    'check': '<:1423392237466681355:1552194563832291368>',
    'ban': '<:1002617024486322356:1555793553114931280>',
    'warning': '<:1418788295361429564:1552144656786002041>',
    'wrench': '<:12009211066101309941:1552328661338689636>',
    'heart': '<:1366143527997935696:1555793537600192512>',
    'announcement': '<:1418786420486836314:1552144609126125578>',
    'badge': '<:975769597309517904:1555793557246189639>',
    'community': '<:975766369503170630:1555793559565893712>',
    'game': '<:1176227736625356971:1555793549713215560>',
    'security': '<:1418788292278751264:1552144638138388570>',
    'online': '<:1418709661737156829:1552151559985692752>',
    'youtube': '<:1423392300423450707:1556072532405256372>',
    'kick': '<:1270252530789515284:1556072535114649650>',
    'tiktok': '<:1423561195256025098:1556072537153347614>',
    'twitch': '<:1423392306429558824:1556072539539898469>',
}
CUSTOM_EMOJI_PATTERN = re.compile(r'<a?:[A-Za-z0-9_]+:(\d+)>')
DEFAULT_EMOJI_PATTERN = re.compile(r'[\U0001f000-\U0001faff\u2600-\u27bf][\ufe0e\ufe0f]?(?:\u200d[\U0001f000-\U0001faff\u2600-\u27bf][\ufe0e\ufe0f]?)*')


def server_emoji_text(text, limit=4096):
    text = str(text)
    budget = limit - len(DEFAULT_EMOJI_PATTERN.sub('', text))
    def replace(match):
        nonlocal budget
        symbol = match.group()[0]
        key = {'🔑': 'key', '🔒': 'shield', '🛡': 'shield', '💡': 'pencil',
               '📝': 'pencil', '✏': 'pencil', '✅': 'check', '✔': 'check',
               '❌': 'ban', '🚫': 'ban', '⚠': 'warning', '🛠': 'wrench',
               '🔧': 'wrench'}.get(symbol, 'document')
        replacement = SERVER_EMOJIS[key]
        if len(replacement) > budget:
            return ''
        budget -= len(replacement)
        return replacement
    return DEFAULT_EMOJI_PATTERN.sub(replace, text)


def unique_embed_emojis(data):
    parts = []
    for name, limit in (('title', 256), ('description', 4096)):
        if name in data:
            parts.append((data, name, limit))
    for field in data.get('fields', []):
        parts.extend(((field, 'name', 256), (field, 'value', 1024)))
    reserved = {match.group(1) for part, name, _ in parts
                for match in CUSTOM_EMOJI_PATTERN.finditer(part[name])}
    used = set()
    for part, name, limit in parts:
        budget = limit - len(part[name])
        def replace(match):
            nonlocal budget
            emoji_id = match.group(1)
            if emoji_id not in used:
                used.add(emoji_id)
                return match.group()
            for candidate in SERVER_EMOJIS.values():
                candidate_id = CUSTOM_EMOJI_PATTERN.fullmatch(candidate).group(1)
                growth = len(candidate) - len(match.group())
                if candidate_id not in reserved and candidate_id not in used and growth <= budget:
                    used.add(candidate_id)
                    budget -= growth
                    return candidate
            # Keep the text when no unused server emoji fits.
            budget += len(match.group())
            return ''
        part[name] = CUSTOM_EMOJI_PATTERN.sub(replace, part[name])


class StudioEmbed(discord.Embed):
    """Use the same studio signature on every generated embed."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_footer()

    def to_dict(self):
        data = super().to_dict()
        for name in ('description',):
            if name in data:
                data[name] = server_emoji_text(data[name])
        if 'fields' in data:
            data['fields'] = [dict(field) for field in data['fields']]
        for field in data.get('fields', []):
            for name in ('name', 'value'):
                field[name] = server_emoji_text(field[name], 256 if name == 'name' else 1024)
        original_title = server_emoji_text(data.get('title') or '')
        existing = CUSTOM_EMOJI_PATTERN.search(original_title)
        title = CUSTOM_EMOJI_PATTERN.sub('', original_title).strip() or '𝙴𝙻𝚈𝚇𝙸𝚄𝙼 𝚂𝚃𝚄𝙳𝙸𝙾'
        if existing:
            emoji = existing.group()
            known = {value.split(':')[1]: value for value in SERVER_EMOJIS.values()}
            emoji = known.get(emoji.split(':')[1], emoji)
        else:
            normalized = ''.join(character for character in unicodedata.normalize('NFKD', title)
                                 if not unicodedata.combining(character)).upper()
            key = 'document'
            for keyword, candidate in (('CODIGO', 'key'), ('VERIFIC', 'shield'),
                                       ('SUGEREN', 'pencil'), ('TICKET', 'announcement'),
                                       ('ERROR', 'warning')):
                if keyword in normalized:
                    key = candidate
                    break
            emoji = SERVER_EMOJIS[key]
        data['title'] = f'{emoji} {title[:256 - len(emoji) - 1]}'
        unique_embed_emojis(data)
        return data

    def set_footer(self, *, text=None, icon_url=None):
        return super().set_footer(text=BRAND_FOOTER, icon_url=BRAND_LOGO)


class ResponsiveView(discord.ui.View):
    async def on_error(self, interaction, error, item):
        logging.error('Button failed: %s', getattr(item, 'custom_id', None),
                      exc_info=(type(error), error, error.__traceback__))
        try:
            message = 'No se pudo completar la accion. Contacta al staff y revisa los permisos del bot.'
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            logging.warning('Interaction expired before error could be delivered')


def configure_console():
    """Force UTF-8 console output when the host supports it."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")


def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)


def read_json(path, default):
    file_path = Path(path)
    if not file_path.exists():
        return default

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path, data):
    """Write JSON atomically to avoid corrupting saved bot state."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = file_path.with_suffix(file_path.suffix + ".tmp")

    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    os.replace(temp_path, file_path)
    from storage import storage
    storage.enqueue(file_path, data)


def update_panel_banners():
    """Migrate existing panels once, after MySQL has restored their JSON copies."""
    marker_path = DATA_DIR / 'appearance_migrations.json'
    migrations = read_json(marker_path, {})
    version = 'panel-banners-2026-10-03-v1'
    if migrations.get(version):
        return
    for filename, banner in (('ticket_configs.json', TICKET_BANNER),
                             ('verification_embeds.json', VERIFICATION_BANNER)):
        path = DATA_DIR / filename
        documents = read_json(path, {})
        for document in documents.values():
            document['image_url'] = banner
        if documents:
            write_json(path, documents)
    migrations[version] = True
    write_json(marker_path, migrations)


def parse_hex_color(color, fallback=discord.Color.blue()):
    if not color:
        return fallback

    try:
        return int(str(color).replace("#", ""), 16)
    except (TypeError, ValueError):
        return fallback


def admin_app_check(admin_role_id):
    def predicate(interaction: discord.Interaction):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return False
        if interaction.user.guild_permissions.administrator:
            return True
        return any(role.id == admin_role_id for role in getattr(interaction.user, "roles", []))

    return app_commands.check(predicate)
