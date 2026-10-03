import json
import os
import sys
from pathlib import Path

import discord
from discord import app_commands


DATA_DIR = Path("data")


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


def parse_hex_color(color, fallback=discord.Color.blue()):
    if not color:
        return fallback

    try:
        return int(str(color).replace("#", ""), 16)
    except (TypeError, ValueError):
        return fallback


def admin_app_check(admin_role_id):
    def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True
        return any(role.id == admin_role_id for role in getattr(interaction.user, "roles", []))

    return app_commands.check(predicate)
