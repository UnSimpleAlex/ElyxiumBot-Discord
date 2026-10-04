import os

import discord
from discord.ext import commands

import captcha
import general_embeds
import ticket
import verificacion
import suggestions
import creators
from common import configure_console, ensure_data_dir, StudioEmbed, update_panel_banners, update_verification_emojis, update_verification_color, update_ticket_option_emojis
from storage import storage


configure_console()
ensure_data_dir()

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", "1431811950794248310"))
TOKEN = os.getenv("DISCORD_TOKEN")


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        super().__init__(
            command_prefix=["!", "/"],
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def setup_hook(self):
        await storage.start()
        update_panel_banners()
        update_verification_emojis()
        update_verification_color()
        update_ticket_option_emojis()
        print("🔄 Configurando sistemas...")

        self._setup_system("embeds", lambda: general_embeds.setup(self, ADMIN_ROLE_ID))
        self._setup_system("tickets", lambda: ticket.setup(self))
        self._setup_system("verificación", lambda: verificacion.setup(self))

        try:
            await verificacion.restore_verification_views(self)
            print("✅ Vistas persistentes de verificación restauradas")
        except Exception as exc:
            print(f"❌ Error restaurando vistas de verificación: {exc}")

        self._setup_system("captcha", lambda: captcha.setup(self))
        self._setup_system("sugerencias", lambda: suggestions.setup(self))
        self._setup_system("creadores", lambda: creators.setup(self))

        synced = await self.tree.sync()
        print(f"✅ {len(synced)} comandos slash globales sincronizados")
        print("ℹ️ Los comandos globales pueden tardar en aparecer. También se sincronizarán por servidor al conectar.")
        self._guild_synced = False

    async def close(self):
        try:
            await storage.close()
        finally:
            await super().close()

    def _setup_system(self, name, setup_callback):
        try:
            setup_callback()
            print(f"✅ Sistema de {name} configurado")
        except Exception as exc:
            print(f"❌ Error al configurar {name}: {exc}")

    async def on_ready(self):
        if not getattr(self, "_guild_synced", False):
            for guild in self.guilds:
                try:
                    self.tree.copy_global_to(guild=guild)
                    synced = await self.tree.sync(guild=guild)
                    print(f"✅ {len(synced)} comandos slash sincronizados en {guild.name} ({guild.id})")
                except Exception as exc:
                    print(f"❌ Error sincronizando comandos en {guild.name}: {exc}")
            self._guild_synced = True

        print(f"{self.user} se ha conectado a Discord!")
        print(f"Bot está en {len(self.guilds)} servidores")
        print("📊 Sistemas activos:")
        print(f"  • Embeds: {general_embeds.count_embeds()}")
        print("  • Verificación: ✅")
        print("  • Captcha: ✅")
        print("  • Tickets: ✅")


bot = Bot()


@bot.tree.command(name="help", description="Muestra todos los comandos disponibles")
async def help_slash(interaction: discord.Interaction):
    embed = StudioEmbed(
        title="🤖 Elyxium Studio - Comandos",
        description="Lista de comandos disponibles:",
        color=discord.Color.blue(),
    )

    embed.add_field(
        name="📝 Comandos de Embeds",
        value="""
        `/config_embed <embed_id>` - Crea o actualiza un embed
        `/editar_embed <embed_id>` - Edita todas las partes de un embed
        `/embed_enviar <canal> <embed_id>` - Envía embed
        `/embed_dm <usuario> <embed_id>` - Envía embed por MD
        `/listar_embeds` - Lista embeds
        `/eliminar_embed <embed_id>` - Elimina embed
        """,
        inline=False,
    )

    embed.add_field(
        name="🔒 Sistema de Verificación",
        value="""
        `/verificacion_setup <canal> <rol> <usar_captcha>` - Configura verificación
        `/verificacion edit_embed <verification_id>` - Edita embed y botón de verificación
        `/verificacion_enviar <canal> <verification_id>` - Envía verificación guardada
        `/verificacion_lista` - Lista configuraciones
        `/captcha_generar <usuario>` - Genera código (admin)
        `/captcha_info` - Ver tu código
        `/captcha_embed_config` - Personaliza el embed del código por MD
        `/captcha_image_config` - Dibuja el código en una imagen del embed
        `/captcha_prompt_config` - Personaliza embed/botón de ingresar código
        `/captcha_embed_preview` - Vista previa del embed captcha
        `/captcha_image_preview` - Vista previa de la imagen captcha
        `/captcha_prompt_preview` - Vista previa del prompt captcha
        """,
        inline=False,
    )

    embed.add_field(
        name="🎫 Sistema de Tickets",
        value="""
        `/ticket_config` - Configura tickets
        `/ticket edit_embed <config_id>` - Edita el embed de tickets
        `/ticket options` - Ver emojis de opciones
        `/ticket edit_options` - Editar emojis de opciones
        `/ticket set_emoji` - Cambiar un emoji enviándolo al chat
        `/ticket set_option_text` - Cambiar título/descripción de opciones
        `/ticket_enviar <canal> [config_id]` - Envía sistema
        `/ticket_stats` - Estadísticas
        """,
        inline=False,
    )

    embed.add_field(
        name="🔑 Captcha",
        value="El usuario presiona **Verificar**, recibe el código por MD si tiene los privados abiertos, y luego pulsa **Ingresar Código**.",
        inline=False,
    )

    embed.add_field(
        name="Sugerencias",
        value="`/sugerencias` o `!sugerencias` - Enviar una idea\n"
              "`/sugerencias_admin acceso` - Canal público y rol de acceso\n"
              "`/sugerencias_admin configurar` - Canales y rol de revisión\n"
              "`/sugerencias_admin panel` - Publicar el panel con botón Sugerir\n"
              "`/sugerencias_admin sincronizar` - Reintentar una publicación\n"
              "`/sugerencias_admin desactivar` - Detener nuevos formularios",
        inline=False,
    )

    embed.add_field(name="Creadores", value="`/directo`, `!directo`, `/video`, `!video` - Panel para anunciar contenido\n"
                    "`/creadores configurar` - Canal y roles Streamer/YouTuber\n"
                    "`/creadores desactivar` - Desactivar anuncios", inline=False)
    embed.set_footer(text="Elyxium Studio - Sistema Completo con Captcha")
    embed.timestamp = discord.utils.utcnow()

    await interaction.response.send_message(embed=embed, ephemeral=True)


if __name__ == "__main__":
    if not TOKEN:
        print("❌ Error: falta DISCORD_TOKEN en el archivo .env")
        raise SystemExit(1)

    print("🚀 Iniciando Elyxium Studio...")
    print("=" * 60)
    print("📦 SISTEMAS INCLUIDOS:")
    print("  ✅ Sistema de Embeds con persistencia")
    print("  ✅ Sistema de Tickets completo")
    print("  ✅ Sistema de Verificación modular")
    print("  ✅ Sistema de Captcha con imagen personalizada")
    print("=" * 60)
    print("📁 Datos en carpeta: data/")
    print("=" * 60)

    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Error: Token de Discord inválido")
    except Exception as exc:
        print(f"❌ Error crítico: {exc}")
