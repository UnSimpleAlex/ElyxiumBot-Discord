import discord
from discord import ui
import os
import random
import string
import time
import io
import ssl
import urllib.request
from datetime import datetime, timedelta
import aiohttp

from common import configure_console, read_json, write_json


configure_console()

# Archivo de persistencia de códigos
CAPTCHA_CODES_FILE = "data/captcha_codes.json"
CAPTCHA_EMBED_CONFIG_FILE = "data/captcha_embed_config.json"
CAPTCHA_PROMPT_CONFIG_FILE = "data/captcha_prompt_config.json"
CAPTCHA_IMAGE_CONFIG_FILE = "data/captcha_image_config.json"
CAPTCHA_MODULE_VERSION = "captcha-image-defer-v2"

# Variables globales
captcha_codes = {}
captcha_embed_config = {
    "title": "🔑 Código de Verificación",
    "description": "Hola {user}, este es tu código para verificarte en **{server}**.\n\nRevisa el código en la imagen.\n\nExpira {expires_relative}.",
    "image_description": "Hola {user}, este es tu código para verificarte en **{server}**.\n\nRevisa el código en la imagen.\n\nExpira {expires_relative}.",
    "color": "#3498db",
    "image_url": None,
    "thumbnail_url": None,
    "footer_text": "Elyxium Studio - Verificación",
    "footer_icon": None,
    "author_name": None,
    "author_icon": None,
    "timestamp": True
}
captcha_prompt_config = {
    "dm_title": "🔒 Verificación con Captcha",
    "dm_description": "Te envié el código por mensaje directo.\n\nCuando lo tengas, presiona **Ingresar Código** aquí para completar la verificación.",
    "dm_color": "#2ecc71",
    "fallback_title": "🔒 Verificación con Captcha",
    "fallback_description": "No pude enviarte un MD, probablemente tienes los mensajes directos cerrados.\n\nTe muestro el código aquí de forma privada. Presiona **Ingresar Código** para completar la verificación.",
    "fallback_color": "#f39c12",
    "button_label": "Ingresar Código",
    "button_emoji": None,
    "timestamp": True
}
captcha_image_config = {
    "enabled": True,
    "background_url": "https://res.cloudinary.com/y08rn1qr/image/upload/v1790175555/captcha.png",
    "fallback_background_url": "assets/captcha_background.png",
    "width": 2244,
    "height": 701,
    "x": 650,
    "y": 325,
    "box_width": 930,
    "box_height": 185,
    "font_size": 108,
    "font_path": "assets/Minecrafter.ttf",
    "pixel_scale": 4,
    "text_color": "#ffffff",
    "shadow": True,
    "shadow_color": "#000000"
}

def generate_code():
    """Genera un código alfanumérico de 6 caracteres"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def save_captcha_codes():
    """Guarda los códigos de captcha"""
    try:
        write_json(CAPTCHA_CODES_FILE, captcha_codes)
        print("✅ Códigos captcha guardados")
    except Exception as e:
        print(f"❌ Error guardando códigos captcha: {e}")

def load_captcha_codes():
    """Carga los códigos de captcha"""
    global captcha_codes
    try:
        if os.path.exists(CAPTCHA_CODES_FILE):
            captcha_codes = read_json(CAPTCHA_CODES_FILE, {})
            # Limpiar códigos expirados al cargar
            clean_expired_codes()
            print(f"✅ {len(captcha_codes)} códigos captcha cargados")
        else:
            captcha_codes = {}
    except Exception as e:
        print(f"❌ Error cargando códigos captcha: {e}")
        captcha_codes = {}

def save_captcha_embed_config():
    """Guarda la configuración del embed de captcha."""
    try:
        write_json(CAPTCHA_EMBED_CONFIG_FILE, captcha_embed_config)
        print("✅ Configuración de embed captcha guardada")
    except Exception as e:
        print(f"❌ Error guardando configuración de embed captcha: {e}")

def load_captcha_embed_config():
    """Carga la configuración del embed de captcha sin romper valores por defecto."""
    global captcha_embed_config
    try:
        if os.path.exists(CAPTCHA_EMBED_CONFIG_FILE):
            stored_config = read_json(CAPTCHA_EMBED_CONFIG_FILE, {})
            captcha_embed_config.update(stored_config)
            sanitize_captcha_embed_config()
            print("✅ Configuración de embed captcha cargada")
        else:
            sanitize_captcha_embed_config()
            save_captcha_embed_config()
    except Exception as e:
        print(f"❌ Error cargando configuración de embed captcha: {e}")

def sanitize_captcha_embed_config():
    """Evita que el código captcha vuelva a mostrarse como texto en el embed."""
    safe_description = "Hola {user}, este es tu código para verificarte en **{server}**.\n\nRevisa el código en la imagen.\n\nExpira {expires_relative}."
    description = captcha_embed_config.get("description") or ""
    image_description = captcha_embed_config.get("image_description") or ""

    if "{code}" in description:
        captcha_embed_config["description"] = safe_description
    if "{code}" in image_description or not image_description:
        captcha_embed_config["image_description"] = safe_description

def save_captcha_prompt_config():
    """Guarda la configuración del embed/botón para ingresar el captcha."""
    try:
        write_json(CAPTCHA_PROMPT_CONFIG_FILE, captcha_prompt_config)
        print("✅ Configuración de prompt captcha guardada")
    except Exception as e:
        print(f"❌ Error guardando configuración de prompt captcha: {e}")

def load_captcha_prompt_config():
    """Carga la configuración del embed/botón para ingresar el captcha."""
    global captcha_prompt_config
    try:
        if os.path.exists(CAPTCHA_PROMPT_CONFIG_FILE):
            stored_config = read_json(CAPTCHA_PROMPT_CONFIG_FILE, {})
            captcha_prompt_config.update(stored_config)
            print("✅ Configuración de prompt captcha cargada")
        else:
            save_captcha_prompt_config()
    except Exception as e:
        print(f"❌ Error cargando configuración de prompt captcha: {e}")

def save_captcha_image_config():
    """Guarda la configuración de la imagen generada del captcha."""
    try:
        write_json(CAPTCHA_IMAGE_CONFIG_FILE, captcha_image_config)
        print("✅ Configuración de imagen captcha guardada")
    except Exception as e:
        print(f"❌ Error guardando configuración de imagen captcha: {e}")

def load_captcha_image_config():
    """Carga la configuración de la imagen generada del captcha."""
    global captcha_image_config
    try:
        if os.path.exists(CAPTCHA_IMAGE_CONFIG_FILE):
            stored_config = read_json(CAPTCHA_IMAGE_CONFIG_FILE, {})
            captcha_image_config.update(stored_config)
            print("✅ Configuración de imagen captcha cargada")
        else:
            save_captcha_image_config()
    except Exception as e:
        print(f"❌ Error cargando configuración de imagen captcha: {e}")

def _format_captcha_text(text, user, guild, result):
    if not text:
        return None

    code = result.get('code')
    if not code and str(user.id) in captcha_codes:
        code = captcha_codes[str(user.id)].get('code')

    expires_seconds = int(result.get('expires_in') or result.get('time_remaining') or 180)
    created_at = result.get('timestamp') or time.time()
    expires_unix = int(created_at + expires_seconds)

    values = {
        "user": user.mention,
        "username": user.display_name,
        "user_id": user.id,
        "server": guild.name if guild else "Discord",
        "code": code or "CÓDIGO_ACTIVO",
        "expires": expires_seconds,
        "expires_unix": expires_unix,
        "expires_relative": f"<t:{expires_unix}:R>",
        "expires_short": f"<t:{expires_unix}:t>",
    }

    try:
        return text.format(**values)
    except (KeyError, ValueError):
        return text

def build_captcha_embed(user, guild, result, use_image_description=False):
    """Construye el embed configurable que recibe el usuario con su código."""
    embed = discord.Embed()
    embed.title = _format_captcha_text(captcha_embed_config.get("title"), user, guild, result)
    description_key = "image_description" if use_image_description else "description"
    description_template = captcha_embed_config.get(description_key) or captcha_embed_config.get("description")
    embed.description = _format_captcha_text(description_template, user, guild, result)

    color = captcha_embed_config.get("color")
    if color:
        try:
            embed.color = int(color.replace("#", ""), 16)
        except ValueError:
            embed.color = discord.Color.blue()
    else:
        embed.color = discord.Color.blue()

    if captcha_embed_config.get("image_url"):
        embed.set_image(url=captcha_embed_config["image_url"])
    if captcha_embed_config.get("thumbnail_url"):
        embed.set_thumbnail(url=captcha_embed_config["thumbnail_url"])
    if captcha_embed_config.get("footer_text"):
        embed.set_footer(
            text=_format_captcha_text(captcha_embed_config["footer_text"], user, guild, result),
            icon_url=captcha_embed_config.get("footer_icon")
        )
    if captcha_embed_config.get("author_name"):
        embed.set_author(
            name=_format_captcha_text(captcha_embed_config["author_name"], user, guild, result),
            icon_url=captcha_embed_config.get("author_icon")
        )
    if captcha_embed_config.get("timestamp", True):
        embed.timestamp = discord.utils.utcnow()

    return embed

def _hex_to_rgb(color, fallback=(255, 255, 255)):
    if not color:
        return fallback
    try:
        color = color.replace("#", "")
        return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return fallback

async def _load_image_bytes(source):
    if not source:
        return None

    if os.path.exists(source):
        try:
            with open(source, "rb") as f:
                return f.read()
        except Exception as e:
            print(f"❌ Error leyendo fondo captcha local: {e}")
            return None

    try:
        headers = {"User-Agent": "ElyxiumStudioBot/1.0"}
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.get(source) as response:
                if response.status == 200:
                    data = await response.read()
                    print(f"✅ Fondo captcha descargado con aiohttp: {len(data)} bytes")
                    return data
                print(f"❌ Fondo captcha respondió HTTP {response.status}: {source}")
    except Exception as e:
        print(f"❌ Error descargando fondo captcha: {e}")

    try:
        connector = aiohttp.TCPConnector(ssl=False)
        headers = {"User-Agent": "ElyxiumStudioBot/1.0"}
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(connector=connector, headers=headers, timeout=timeout) as session:
            async with session.get(source) as response:
                if response.status == 200:
                    data = await response.read()
                    print(f"✅ Fondo captcha descargado con aiohttp sin SSL estricto: {len(data)} bytes")
                    return data
                print(f"❌ Fondo captcha respondió HTTP {response.status} sin SSL estricto: {source}")
    except Exception as e:
        print(f"❌ Error descargando fondo captcha sin SSL estricto: {e}")

    try:
        request = urllib.request.Request(
            source,
            headers={
                "User-Agent": "ElyxiumStudioBot/1.0",
                "Accept": "image/png,image/*;q=0.9,*/*;q=0.8",
            },
        )
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, timeout=15, context=context) as response:
            status = getattr(response, "status", 200)
            if status == 200:
                data = response.read()
                print(f"✅ Fondo captcha descargado con urllib: {len(data)} bytes")
                return data
            print(f"❌ Fondo captcha respondió HTTP {status} con urllib: {source}")
    except Exception as e:
        print(f"❌ Error descargando fondo captcha con urllib: {e}")
    return None

async def build_captcha_image_file(result):
    """Genera un PNG con el código dibujado en la posición configurada."""
    if not captcha_image_config.get("enabled", False):
        print("ℹ️ Imagen captcha desactivada en data/captcha_image_config.json")
        return None

    code = result.get("code")
    if not code:
        print("❌ No se pudo generar imagen captcha: falta result['code']")
        return None

    try:
        from PIL import Image
    except ImportError:
        print("❌ Pillow no está instalado. Instala requirements.txt para generar imágenes captcha.")
        return None

    width = int(captcha_image_config.get("width") or 900)
    height = int(captcha_image_config.get("height") or 300)
    background_url = captcha_image_config.get("background_url") or captcha_embed_config.get("image_url")
    background_bytes = await _load_image_bytes(background_url)
    if not background_bytes and captcha_image_config.get("fallback_background_url"):
        background_bytes = await _load_image_bytes(captcha_image_config.get("fallback_background_url"))

    if background_bytes:
        try:
            image = Image.open(io.BytesIO(background_bytes)).convert("RGBA")
            image = image.resize((width, height))
        except Exception:
            print("❌ No se pudo abrir el fondo captcha; usando fondo simple.")
            image = Image.new("RGBA", (width, height), (25, 28, 35, 255))
    else:
        print("ℹ️ No se encontró fondo captcha; usando fondo simple.")
        image = Image.new("RGBA", (width, height), (25, 28, 35, 255))

    font_size = int(captcha_image_config.get("font_size") or 64)

    box_x = int(captcha_image_config.get("x") or 0)
    box_y = int(captcha_image_config.get("y") or 0)
    box_width = int(captcha_image_config.get("box_width") or max(1, width - box_x))
    box_height = int(captcha_image_config.get("box_height") or max(1, height - box_y))
    text_color = _hex_to_rgb(captcha_image_config.get("text_color"), (255, 255, 255))
    text_image = _render_captcha_text(code, text_color, font_size)

    x = box_x + max(0, (box_width - text_image.width) // 2)
    y = box_y + max(0, (box_height - text_image.height) // 2)

    if captcha_image_config.get("shadow", True):
        shadow_color = _hex_to_rgb(captcha_image_config.get("shadow_color"), (0, 0, 0))
        shadow_image = _render_captcha_text(code, shadow_color, font_size)
        shadow_offset = max(4, font_size // 16)
        image.alpha_composite(shadow_image, (x + shadow_offset, y + shadow_offset))

    image.alpha_composite(text_image, (x, y))

    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return discord.File(output, filename="captcha.png")

PIXEL_FONT = {
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
    "A": ["111", "101", "111", "101", "101"],
    "B": ["110", "101", "110", "101", "110"],
    "C": ["111", "100", "100", "100", "111"],
    "D": ["110", "101", "101", "101", "110"],
    "E": ["111", "100", "111", "100", "111"],
    "F": ["111", "100", "111", "100", "100"],
    "G": ["111", "100", "101", "101", "111"],
    "H": ["101", "101", "111", "101", "101"],
    "I": ["111", "010", "010", "010", "111"],
    "J": ["001", "001", "001", "101", "111"],
    "K": ["101", "101", "110", "101", "101"],
    "L": ["100", "100", "100", "100", "111"],
    "M": ["101", "111", "111", "101", "101"],
    "N": ["101", "111", "111", "111", "101"],
    "O": ["111", "101", "101", "101", "111"],
    "P": ["111", "101", "111", "100", "100"],
    "Q": ["111", "101", "101", "111", "001"],
    "R": ["111", "101", "111", "110", "101"],
    "S": ["111", "100", "111", "001", "111"],
    "T": ["111", "010", "010", "010", "010"],
    "U": ["101", "101", "101", "101", "111"],
    "V": ["101", "101", "101", "101", "010"],
    "W": ["101", "101", "111", "111", "101"],
    "X": ["101", "101", "010", "101", "101"],
    "Y": ["101", "101", "010", "010", "010"],
    "Z": ["111", "001", "010", "100", "111"],
}

def _render_captcha_text(text, fill, font_size):
    font_path = captcha_image_config.get("font_path")
    if font_path and os.path.exists(font_path):
        return _render_truetype_captcha_text(text, fill, font_size, font_path)

    if font_path:
        print(f"ℹ️ Fuente captcha no encontrada: {font_path}. Usando fuente pixel fallback.")
    return _render_minecraft_text(text, fill, font_size)

def _render_truetype_captcha_text(text, fill, font_size, font_path):
    from PIL import Image, ImageDraw, ImageFont

    text = str(text).upper()
    font = ImageFont.truetype(font_path, font_size)
    measure = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    measure_draw = ImageDraw.Draw(measure)
    stroke_width = int(captcha_image_config.get("font_stroke_width") or 0)
    bbox = measure_draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    padding = max(8, font_size // 8)
    width = max(1, bbox[2] - bbox[0] + padding * 2)
    height = max(1, bbox[3] - bbox[1] + padding * 2)

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.text(
        (padding - bbox[0], padding - bbox[1]),
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=fill,
    )
    return image

def _render_minecraft_text(text, fill, font_size):
    from PIL import Image, ImageDraw

    text = str(text).upper()
    pixel = max(9, font_size // 6)
    gap = max(2, pixel // 4)
    letter_gap = max(12, pixel)
    padding = pixel

    glyphs = [PIXEL_FONT.get(char, PIXEL_FONT["0"]) for char in text]
    width = padding * 2
    for glyph in glyphs:
        width += len(glyph[0]) * pixel + (len(glyph[0]) - 1) * gap + letter_gap
    width = max(1, width - letter_gap)
    height = padding * 2 + 5 * pixel + 4 * gap

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    cursor_x = padding

    for glyph in glyphs:
        for row_index, row in enumerate(glyph):
            for col_index, value in enumerate(row):
                if value != "1":
                    continue
                x1 = cursor_x + col_index * (pixel + gap)
                y1 = padding + row_index * (pixel + gap)
                x2 = x1 + pixel
                y2 = y1 + pixel
                draw.rectangle((x1, y1, x2, y2), fill=fill)
        cursor_x += len(glyph[0]) * pixel + (len(glyph[0]) - 1) * gap + letter_gap

    return image

async def build_captcha_embed_message(user, guild, result):
    """Devuelve embed + archivo opcional para enviar el código captcha."""
    file = await build_captcha_image_file(result)
    image_mode = bool(file) or captcha_image_config.get("enabled", False)
    embed = build_captcha_embed(user, guild, result, use_image_description=image_mode)
    if file:
        embed.set_image(url="attachment://captcha.png")
    return embed, file

def _parse_color(color, fallback):
    if color:
        try:
            return int(color.replace("#", ""), 16)
        except ValueError:
            return fallback
    return fallback

def build_captcha_prompt_embed(user, guild, dm_sent=True):
    """Construye el embed temporal que muestra el botón para ingresar el código."""
    prefix = "dm" if dm_sent else "fallback"
    embed = discord.Embed()
    embed.title = _format_captcha_text(captcha_prompt_config.get(f"{prefix}_title"), user, guild, {})
    embed.description = _format_captcha_text(captcha_prompt_config.get(f"{prefix}_description"), user, guild, {})
    embed.color = _parse_color(
        captcha_prompt_config.get(f"{prefix}_color"),
        discord.Color.green().value if dm_sent else discord.Color.orange().value
    )

    if captcha_prompt_config.get("timestamp", True):
        embed.timestamp = discord.utils.utcnow()

    return embed

def parse_captcha_emoji(emoji_text):
    if not emoji_text:
        return None
    try:
        return discord.PartialEmoji.from_str(emoji_text)
    except Exception:
        return emoji_text

def get_captcha_entry_button_label():
    return captcha_prompt_config.get("button_label") or "Ingresar Código"

def get_captcha_entry_button_emoji():
    return captcha_prompt_config.get("button_emoji")

def clean_expired_codes():
    """Limpia códigos expirados (más de 3 minutos)"""
    current_time = time.time()
    expired = []
    
    for user_id, data in captcha_codes.items():
        if current_time - data.get('timestamp', 0) > 180:  # 3 minutos
            expired.append(user_id)
    
    for user_id in expired:
        del captcha_codes[user_id]
    
    if expired:
        save_captcha_codes()
        print(f"🧹 {len(expired)} códigos expirados eliminados")

def create_captcha_code(user_id: str):
    """Crea un código de captcha para un usuario"""
    clean_expired_codes()
    
    # Verificar si ya tiene un código válido
    if user_id in captcha_codes:
        time_diff = time.time() - captcha_codes[user_id]['timestamp']
        if time_diff < 180:  # Menos de 3 minutos
            return {
                'success': False,
                'message': 'Ya tienes un código activo. Espera a que expire.',
                'code': captcha_codes[user_id].get('code'),
                'timestamp': captcha_codes[user_id].get('timestamp'),
                'time_remaining': int(180 - time_diff)
            }
    
    # Generar nuevo código
    code = generate_code()
    captcha_codes[user_id] = {
        'code': code,
        'timestamp': time.time(),
        'used': False
    }
    
    save_captcha_codes()
    
    return {
        'success': True,
        'code': code,
        'timestamp': captcha_codes[user_id]['timestamp'],
        'expires_in': 180  # 3 minutos
    }

def verify_captcha_code(user_id: str, code: str):
    """Verifica un código de captcha"""
    clean_expired_codes()
    
    if user_id not in captcha_codes:
        return {
            'success': False,
            'message': 'No se encontró código para este usuario. Genera uno nuevo.'
        }
    
    data = captcha_codes[user_id]
    
    # Verificar si ya fue usado
    if data.get('used', False):
        return {
            'success': False,
            'message': 'Este código ya fue utilizado.'
        }
    
    # Verificar si expiró
    time_diff = time.time() - data['timestamp']
    if time_diff > 180:
        del captcha_codes[user_id]
        save_captcha_codes()
        return {
            'success': False,
            'message': 'El código ha expirado. Genera uno nuevo.'
        }
    
    # Verificar código
    if data['code'].upper() == code.upper():
        captcha_codes[user_id]['used'] = True
        save_captcha_codes()
        return {
            'success': True,
            'message': 'Código verificado correctamente.'
        }
    else:
        return {
            'success': False,
            'message': 'Código incorrecto. Intenta nuevamente.'
        }

class CaptchaModal(ui.Modal):
    def __init__(self, role: discord.Role, user: discord.User):
        super().__init__(title="Verificación con Captcha", timeout=300)
        self.role = role
        self.user = user
        
        self.code_input = ui.TextInput(
            label="Código de Verificación",
            placeholder="Ingresa tu código de 6 caracteres",
            min_length=6,
            max_length=6,
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.code_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(self.user.id)
        code = self.code_input.value
        
        # Verificar código
        result = verify_captcha_code(user_id, code)
        
        if result['success']:
            try:
                await interaction.user.add_roles(self.role)
                
                embed = discord.Embed(
                    title="✅ Verificación Exitosa",
                    description=f"¡Felicidades! Has sido verificado correctamente.\n\nSe te ha asignado el rol: **{self.role.name}**",
                    color=discord.Color.green()
                )
                embed.set_footer(text="Bienvenido a la comunidad")
                embed.timestamp = discord.utils.utcnow()
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ Error: El bot no tiene permisos para asignar roles.",
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ Error al asignar el rol: {e}",
                    ephemeral=True
                )
        else:
            embed = discord.Embed(
                title="❌ Verificación Fallida",
                description=result['message'],
                color=discord.Color.red()
            )
            
            if 'No se encontró código' in result['message'] or 'expirado' in result['message']:
                embed.add_field(
                    name="📝 Genera tu código",
                    value="Presiona nuevamente el botón de verificación para recibir un nuevo código.",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

def setup_captcha_api():
    """Configura endpoints para la API web"""
    # Esta función será usada por el servidor web Flask/FastAPI
    return {
        'create_code': create_captcha_code,
        'verify_code': verify_captcha_code,
        'get_code_info': lambda user_id: captcha_codes.get(user_id, None)
    }

def setup(bot):
    """Inicializa el sistema de captcha"""
    print("🔧 Configurando sistema de captcha...")
    print(f"🧩 Captcha module version: {CAPTCHA_MODULE_VERSION}")
    load_captcha_codes()
    load_captcha_embed_config()
    load_captcha_prompt_config()
    load_captcha_image_config()

    @bot.tree.command(name="captcha_embed_config", description="[ADMIN] Configura el embed que se envía por MD con el código captcha")
    @discord.app_commands.describe(
        titulo="Título del embed. Placeholders: {user}, {username}, {server}, {code}, {expires}",
        descripcion="Descripción del embed. Placeholders: {user}, {username}, {server}, {code}, {expires}",
        color="Color hexadecimal, ejemplo: #3498db",
        imagen="URL de imagen principal",
        miniatura="URL de miniatura",
        footer="Texto del footer",
        timestamp="Mostrar fecha/hora en el embed"
    )
    async def captcha_embed_config_command(
        interaction: discord.Interaction,
        titulo: str = None,
        descripcion: str = None,
        color: str = None,
        imagen: str = None,
        miniatura: str = None,
        footer: str = None,
        timestamp: bool = None
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo administradores pueden usar este comando.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        if titulo is not None:
            captcha_embed_config["title"] = titulo
        if descripcion is not None:
            captcha_embed_config["description"] = descripcion
        if color is not None:
            captcha_embed_config["color"] = color
        if imagen is not None:
            captcha_embed_config["image_url"] = imagen or None
        if miniatura is not None:
            captcha_embed_config["thumbnail_url"] = miniatura or None
        if footer is not None:
            captcha_embed_config["footer_text"] = footer or None
        if timestamp is not None:
            captcha_embed_config["timestamp"] = timestamp

        save_captcha_embed_config()
        preview_result = {"success": True, "code": "ABC123", "expires_in": 180}
        preview_embed, preview_file = await build_captcha_embed_message(interaction.user, interaction.guild, preview_result)
        await interaction.followup.send(
            "✅ Configuración del embed captcha guardada.\n**Vista previa:**",
            embed=preview_embed,
            file=preview_file,
            ephemeral=True
        )

    @bot.tree.command(name="captcha_embed_preview", description="[ADMIN] Muestra una vista previa del embed captcha")
    async def captcha_embed_preview(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo administradores pueden usar este comando.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        load_captcha_embed_config()
        load_captcha_image_config()
        preview_result = {"success": True, "code": "ABC123", "expires_in": 180}
        preview_embed, preview_file = await build_captcha_embed_message(interaction.user, interaction.guild, preview_result)
        await interaction.followup.send(
            "**Vista previa del embed captcha:**",
            embed=preview_embed,
            file=preview_file,
            ephemeral=True
        )

    @bot.tree.command(name="captcha_image_config", description="[ADMIN] Configura la imagen generada con el código captcha")
    @discord.app_commands.describe(
        activado="Activar/desactivar imagen generada con el código",
        x="Posición X del código",
        y="Posición Y del código",
        ancho="Ancho de la imagen",
        alto="Alto de la imagen",
        ancho_caja="Ancho del área donde se centra el código",
        alto_caja="Alto del área donde se centra el código",
        tamano_fuente="Tamaño del texto del código",
        color_texto="Color del código. Ej: #ffffff",
        fondo_url="URL de fondo. Si queda vacío usa imagen del embed o fondo simple",
        sombra="Activar sombra del texto"
    )
    async def captcha_image_config_command(
        interaction: discord.Interaction,
        activado: bool = None,
        x: int = None,
        y: int = None,
        ancho: int = None,
        alto: int = None,
        ancho_caja: int = None,
        alto_caja: int = None,
        tamano_fuente: int = None,
        color_texto: str = None,
        fondo_url: str = None,
        sombra: bool = None
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo administradores pueden usar este comando.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        if activado is not None:
            captcha_image_config["enabled"] = activado
        if x is not None:
            captcha_image_config["x"] = max(0, x)
        if y is not None:
            captcha_image_config["y"] = max(0, y)
        if ancho is not None:
            captcha_image_config["width"] = max(100, ancho)
        if alto is not None:
            captcha_image_config["height"] = max(100, alto)
        if ancho_caja is not None:
            captcha_image_config["box_width"] = max(20, ancho_caja)
        if alto_caja is not None:
            captcha_image_config["box_height"] = max(20, alto_caja)
        if tamano_fuente is not None:
            captcha_image_config["font_size"] = max(8, tamano_fuente)
        if color_texto is not None:
            captcha_image_config["text_color"] = color_texto
        if fondo_url is not None:
            captcha_image_config["background_url"] = fondo_url or None
        if sombra is not None:
            captcha_image_config["shadow"] = sombra

        save_captcha_image_config()
        preview_result = {"success": True, "code": "ABC123", "expires_in": 180}
        preview_embed, preview_file = await build_captcha_embed_message(interaction.user, interaction.guild, preview_result)
        await interaction.followup.send(
            "✅ Configuración de imagen captcha guardada.\n**Vista previa:**",
            embed=preview_embed,
            file=preview_file,
            ephemeral=True
        )

    @bot.tree.command(name="captcha_image_preview", description="[ADMIN] Vista previa de la imagen generada del captcha")
    async def captcha_image_preview(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo administradores pueden usar este comando.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        preview_result = {"success": True, "code": "ABC123", "expires_in": 180}
        preview_embed, preview_file = await build_captcha_embed_message(interaction.user, interaction.guild, preview_result)
        status = "✅ Imagen captcha generada y adjunta." if preview_file else "❌ La imagen captcha no se generó. Revisa consola: Pillow, enabled o fondo."
        await interaction.followup.send(
            f"**Vista previa de la imagen captcha:**\n{status}",
            embed=preview_embed,
            file=preview_file,
            ephemeral=True
        )

    @bot.tree.command(name="captcha_prompt_config", description="[ADMIN] Configura el embed y botón para ingresar el código captcha")
    @discord.app_commands.describe(
        dm_titulo="Título cuando el código se envía por MD",
        dm_descripcion="Descripción cuando el código se envía por MD",
        dm_color="Color cuando se envía por MD. Ej: #2ecc71",
        fallback_titulo="Título cuando no se puede enviar MD",
        fallback_descripcion="Descripción cuando no se puede enviar MD",
        fallback_color="Color cuando no se puede enviar MD. Ej: #f39c12",
        boton_texto="Texto del botón para ingresar el código",
        boton_emoji="Emoji del botón. Ej: 🔑 o <:codigo:123>",
        timestamp="Mostrar fecha/hora en el embed"
    )
    async def captcha_prompt_config_command(
        interaction: discord.Interaction,
        dm_titulo: str = None,
        dm_descripcion: str = None,
        dm_color: str = None,
        fallback_titulo: str = None,
        fallback_descripcion: str = None,
        fallback_color: str = None,
        boton_texto: str = None,
        boton_emoji: str = None,
        timestamp: bool = None
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo administradores pueden usar este comando.", ephemeral=True)
            return

        if dm_titulo is not None:
            captcha_prompt_config["dm_title"] = dm_titulo
        if dm_descripcion is not None:
            captcha_prompt_config["dm_description"] = dm_descripcion
        if dm_color is not None:
            captcha_prompt_config["dm_color"] = dm_color
        if fallback_titulo is not None:
            captcha_prompt_config["fallback_title"] = fallback_titulo
        if fallback_descripcion is not None:
            captcha_prompt_config["fallback_description"] = fallback_descripcion
        if fallback_color is not None:
            captcha_prompt_config["fallback_color"] = fallback_color
        if boton_texto is not None:
            captcha_prompt_config["button_label"] = boton_texto[:80] or "Ingresar Código"
        if boton_emoji is not None:
            captcha_prompt_config["button_emoji"] = boton_emoji or None
        if timestamp is not None:
            captcha_prompt_config["timestamp"] = timestamp

        save_captcha_prompt_config()
        await interaction.response.send_message(
            "✅ Configuración del embed/botón de ingresar código guardada.\n**Vista previa cuando el MD sí se envía:**",
            embed=build_captcha_prompt_embed(interaction.user, interaction.guild, True),
            ephemeral=True
        )

    @bot.tree.command(name="captcha_prompt_preview", description="[ADMIN] Vista previa del embed/botón para ingresar código")
    async def captcha_prompt_preview(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo administradores pueden usar este comando.", ephemeral=True)
            return

        await interaction.response.send_message(
            "**Vista previa cuando el MD sí se envía:**",
            embed=build_captcha_prompt_embed(interaction.user, interaction.guild, True),
            ephemeral=True
        )
        await interaction.followup.send(
            "**Vista previa cuando el MD falla:**",
            embed=build_captcha_prompt_embed(interaction.user, interaction.guild, False),
            ephemeral=True
        )
    
    # Comando para generar código manualmente desde Discord (admin)
    @bot.tree.command(name="captcha_generar", description="[ADMIN] Genera un código de captcha para un usuario")
    @discord.app_commands.describe(usuario="Usuario para el que generar el código")
    async def captcha_generar(interaction: discord.Interaction, usuario: discord.User):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo administradores pueden usar este comando.", ephemeral=True)
            return
        
        result = create_captcha_code(str(usuario.id))
        
        if result['success']:
            embed = discord.Embed(
                title="🔑 Código Generado",
                description=f"Código para {usuario.mention}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Código", value=f"```{result['code']}```", inline=False)
            embed.add_field(name="Expira en", value=f"{result['expires_in']} segundos", inline=False)
            embed.set_footer(text="Este código es de un solo uso")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                f"❌ {result['message']}\n⏰ Tiempo restante: {result.get('time_remaining', 0)} segundos",
                ephemeral=True
            )
    
    @bot.tree.command(name="captcha_info", description="Ver información de tu código de captcha")
    async def captcha_info(interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        clean_expired_codes()
        
        if user_id not in captcha_codes:
            embed = discord.Embed(
                title="ℹ️ Sin Código Activo",
                description="No tienes un código de verificación activo.",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="📝 Genera tu código",
                value="Presiona el botón de verificación del servidor para recibir un código.",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        data = captcha_codes[user_id]
        time_elapsed = time.time() - data['timestamp']
        time_remaining = max(0, 180 - int(time_elapsed))
        
        status = "✅ Usado" if data.get('used', False) else "⏳ Pendiente"
        
        embed = discord.Embed(
            title="🔑 Tu Código de Captcha",
            color=discord.Color.blue() if not data.get('used', False) else discord.Color.green()
        )
        embed.add_field(name="Estado", value=status, inline=True)
        embed.add_field(name="⏰ Tiempo restante", value=f"{time_remaining}s", inline=True)
        
        if not data.get('used', False) and time_remaining > 0:
            embed.add_field(name="Código", value=f"```{data['code']}```", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    print("✅ Sistema de captcha configurado")
