import json
import logging
import os
import sys
from pathlib import Path

import discord
from discord import app_commands


DATA_DIR = Path("data")
BRAND_FOOTER = '© Elyxium Studio Copyright 2026'
BRAND_LOGO = 'https://cdn.discordapp.com/avatars/1418452578102153226/0511c1a0b2562146e0f4cc69aa9cea02.png'


class StudioEmbed(discord.Embed):
    """Use the same studio signature on every generated embed."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_footer()

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
