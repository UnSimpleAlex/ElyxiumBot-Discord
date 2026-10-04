import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
from discord.ext import commands

import minecraft_info
from common import BRAND_FOOTER, BRAND_LOGO, CUSTOM_EMOJI_PATTERN


class MinecraftInfoTests(unittest.IsolatedAsyncioTestCase):
    async def test_embed_has_exact_connection_details_banner_and_unique_server_emojis(self):
        data = minecraft_info.build_server_embed().to_dict()
        self.assertEqual(data['image']['url'], minecraft_info.SERVER_BANNER)
        self.assertEqual(data['footer'], {'text': BRAND_FOOTER, 'icon_url': BRAND_LOGO})
        text = data['title'] + data['description'] + ''.join(field['name'] + field['value'] for field in data['fields'])
        self.assertIn('play.elyxium.online', text)
        self.assertIn('1.21.11', text)
        self.assertIn('JAVA EDITION', text)
        self.assertNotIn('BEDROCK', text)
        ids = CUSTOM_EMOJI_PATTERN.findall(text)
        self.assertEqual(len(ids), 5)
        self.assertEqual(len(ids), len(set(ids)))

    async def test_both_commands_are_public_and_use_the_same_embed(self):
        bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())
        try:
            minecraft_info.setup(bot)
            slash = bot.tree.get_command('ip')
            prefix = bot.get_command('ip')
            self.assertEqual(slash.checks, [])
            self.assertEqual(prefix.checks, [])
            interaction = SimpleNamespace(response=SimpleNamespace(send_message=AsyncMock()))
            ctx = SimpleNamespace(send=AsyncMock())
            await slash.callback(interaction)
            await prefix.callback(ctx)
            self.assertEqual(interaction.response.send_message.await_args.kwargs['embed'].to_dict(),
                             ctx.send.await_args.kwargs['embed'].to_dict())
        finally:
            await bot.close()


if __name__ == '__main__':
    unittest.main()
