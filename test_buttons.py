import unittest
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from verificacion import VerificationView
from common import ResponsiveView
import captcha


class VerificationButtonTests(unittest.IsolatedAsyncioTestCase):
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


if __name__ == '__main__':
    unittest.main()
