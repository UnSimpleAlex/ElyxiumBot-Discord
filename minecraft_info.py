"""Public Minecraft connection details shared by slash and prefix commands."""
import discord

from common import SERVER_EMOJIS, StudioEmbed


JAVA_ADDRESS = 'play.elyxium.online'
JAVA_VERSION = '1.21.11'
SERVER_BANNER = 'https://res.cloudinary.com/y08rn1qr/image/upload/v1791077024/f3e12f2b-7a3d-4d1e-8fb8-45dde364a6d2.png'


def build_server_embed():
    embed = StudioEmbed(title=f"{SERVER_EMOJIS['game']} 𝙼𝙸𝙽𝙴𝙲𝚁𝙰𝙵𝚃 · 𝙴𝙻𝚈𝚇𝙸𝚄𝙼 𝚂𝚃𝚄𝙳𝙸𝙾",
                        description=f"{SERVER_EMOJIS['announcement']} **TU AVENTURA COMIENZA AQUÍ**\n\n"
                                    'Conecta a nuestro servidor de **MINECRAFT JAVA** y comparte la experiencia con la comunidad.',
                        color=0x2ECC71)
    embed.add_field(name=f"{SERVER_EMOJIS['community']} DIRECCIÓN DEL SERVIDOR", value=f'```{JAVA_ADDRESS}```', inline=False)
    embed.add_field(name=f"{SERVER_EMOJIS['badge']} VERSIÓN", value=f'**{JAVA_VERSION}**', inline=True)
    embed.add_field(name=f"{SERVER_EMOJIS['document']} EDICIÓN", value='**JAVA EDITION**', inline=True)
    embed.set_image(url=SERVER_BANNER)
    return embed


def setup(bot):
    @bot.tree.command(name='ip', description='Muestra la IP y versión del servidor de Minecraft Java')
    async def ip_slash(interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_server_embed(), allowed_mentions=discord.AllowedMentions.none())

    @bot.command(name='ip')
    async def ip_prefix(ctx):
        await ctx.send(embed=build_server_embed(), allowed_mentions=discord.AllowedMentions.none())
