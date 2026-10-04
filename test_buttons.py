import unittest
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from verificacion import VerificationView
from common import ResponsiveView, SERVER_EMOJIS
import captcha
import verificacion
from discord.ext import commands


class VerificationButtonTests(unittest.IsolatedAsyncioTestCase):
    async def test_verification_button_uses_server_emoji_for_defaults_and_legacy_unicode(self):
        for emoji in (None, '✅', SERVER_EMOJIS['check']):
            view = VerificationView(20, button_emoji=emoji)
            self.assertEqual(str(view.verify.emoji), SERVER_EMOJIS['check'])
            self.assertIsNotNone(view.verify.emoji.id)

    async def test_saved_button_migration_preserves_custom_emojis_and_properties(self):
        stored = {'verification_1': {'emoji': '✅', 'label': 'Verificar'},
                  'verification_2': {'emoji': SERVER_EMOJIS['shield']}}
        with patch('verificacion.verification_buttons', {}), patch.dict(verificacion.verification_embeds, {'verification_3': {}}, clear=True), \
             patch('verificacion.os.path.exists', return_value=True), patch('verificacion.read_json', return_value=stored), \
             patch('verificacion.save_verification_buttons') as save:
            verificacion.load_verification_buttons()
            self.assertEqual(stored['verification_1'], {'emoji': SERVER_EMOJIS['check'], 'label': 'Verificar'})
            self.assertEqual(stored['verification_2']['emoji'], SERVER_EMOJIS['shield'])
            self.assertEqual(stored['verification_3']['emoji'], SERVER_EMOJIS['check'])
            save.assert_called_once()

    def interaction(self):
        role = MagicMock()
        role.id = 20
        role.name = 'verified'
        role.managed = False
        role.is_default.return_value = False
        role.__ge__.return_value = False
        user = MagicMock(spec=discord.Member)
        user.id = 1
        user.roles = []
        user.add_roles = AsyncMock()
        user.send = AsyncMock()
        guild = MagicMock()
        guild.id = 10
        guild.get_role.return_value = role
        guild.me.guild_permissions.manage_roles = True
        return SimpleNamespace(
            user=user, guild=guild,
            response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock(), is_done=lambda: True),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    async def test_direct_verification_acknowledges_before_role_request(self):
        interaction = self.interaction()
        async def assign(role):
            interaction.response.defer.assert_awaited_once()
        interaction.user.add_roles.side_effect = assign
        await VerificationView(20).verify.callback(interaction)
        interaction.user.add_roles.assert_awaited_once()
        interaction.followup.send.assert_awaited_once()

    async def test_missing_permissions_returns_actionable_response(self):
        interaction = self.interaction()
        interaction.guild.me.guild_permissions.manage_roles = False
        await VerificationView(20).verify.callback(interaction)
        interaction.response.defer.assert_awaited_once()
        interaction.followup.send.assert_awaited_once()
        interaction.user.add_roles.assert_not_awaited()

    async def test_active_captcha_does_not_send_another_dm(self):
        interaction = self.interaction()
        with patch('captcha.create_captcha_code', return_value={'success': False, 'message': 'Codigo activo'}):
            await VerificationView(20, use_captcha=True).verify.callback(interaction)
        interaction.response.defer.assert_awaited_once()
        interaction.user.send.assert_not_awaited()
        interaction.followup.send.assert_awaited_once()

    async def test_captcha_rendering_starts_after_acknowledgement(self):
        interaction = self.interaction()
        async def render(*args):
            interaction.response.defer.assert_awaited_once()
            return discord.Embed(title='captcha'), None
        with patch('captcha.create_captcha_code', return_value={'success': True}), \
             patch('captcha.build_captcha_embed_message', side_effect=render), \
             patch('captcha.build_captcha_prompt_embed', return_value=discord.Embed(title='enter')):
            await VerificationView(20, use_captcha=True).verify.callback(interaction)
        interaction.user.send.assert_awaited_once()
        interaction.followup.send.assert_awaited_once()

    async def test_button_error_after_defer_uses_followup(self):
        interaction = self.interaction()
        with self.assertLogs(level='ERROR'):
            await ResponsiveView().on_error(interaction, RuntimeError('test'), SimpleNamespace(custom_id='verify'))
        interaction.followup.send.assert_awaited_once()
        interaction.response.send_message.assert_not_awaited()

    async def test_image_rendering_runs_outside_discord_thread(self):
        main_thread = threading.get_ident()
        def render(*args):
            self.assertNotEqual(threading.get_ident(), main_thread)
            return 'image'
        with patch.dict(captcha.captcha_image_config, {'enabled': True}), \
             patch('captcha._load_image_bytes', new=AsyncMock(return_value=b'background')), \
             patch('captcha._render_captcha_image', side_effect=render):
            self.assertEqual(await captcha.build_captcha_image_file({'code': 'ABC123'}), 'image')

    async def test_unknown_legacy_button_gets_repair_message(self):
        interaction = self.interaction()
        interaction.type = discord.InteractionType.component
        interaction.data = {'custom_id': 'verify_button_verification_1'}
        interaction.client = SimpleNamespace(persistent_views=[VerificationView(20, 'verify_button_verification_2')])
        interaction.response.is_done = lambda: False
        await verificacion.respond_to_unregistered_verification(interaction)
        interaction.response.send_message.assert_awaited_once()
        interaction.user.add_roles.assert_not_awaited()

    async def test_registered_button_is_not_answered_twice(self):
        interaction = self.interaction()
        interaction.type = discord.InteractionType.component
        interaction.data = {'custom_id': 'verify_button_verification_2'}
        interaction.client = SimpleNamespace(persistent_views=[VerificationView(20, 'verify_button_verification_2')])
        interaction.response.is_done = lambda: False
        await verificacion.respond_to_unregistered_verification(interaction)
        interaction.response.send_message.assert_not_awaited()

    async def test_repair_keeps_original_message_and_restores_callback(self):
        interaction = self.interaction()
        bot = commands.Bot(command_prefix='!', intents=discord.Intents.none())
        bot._connection.user = SimpleNamespace(id=55)
        role = interaction.guild.get_role(20)
        role.guild = interaction.guild
        button = MagicMock(spec=discord.Button)
        button.custom_id = 'verify_button_verification_1'
        button.emoji = None
        message = SimpleNamespace(id=123, author=SimpleNamespace(id=55),
                                  components=[SimpleNamespace(children=[button])])
        channel = SimpleNamespace(id=99, guild=interaction.guild, fetch_message=AsyncMock(return_value=message))
        try:
            verificacion.setup_verification_commands(bot)
            with patch.dict(verificacion.verification_roles, {}, clear=True), \
                 patch('verificacion.write_json') as save, patch('storage.storage.pool', None):
                await bot.tree.get_command('verificacion_reparar').callback(interaction, channel, '123', role, True)
                save.assert_called_once()
                self.assertEqual(verificacion.verification_roles[button.custom_id]['message_id'], 123)
                self.assertTrue(any(view.children[0].custom_id == button.custom_id for view in bot.persistent_views))
        finally:
            await bot.close()


if __name__ == '__main__':
    unittest.main()
