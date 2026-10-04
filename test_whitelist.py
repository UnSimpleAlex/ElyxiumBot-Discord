import asyncio
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

import whitelist
from common import BRAND_FOOTER, CUSTOM_EMOJI_PATTERN


class WhitelistTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        writer = patch('whitelist.write_json')
        self.save = writer.start()
        self.addCleanup(writer.stop)
        with patch('whitelist.read_json', return_value={}):
            self.service = whitelist.WhitelistService(MagicMock())
        self.service.config = {'10': {'enabled': True, 'channel_id': 100, 'message_id': 200}}
        user = MagicMock(spec=discord.Member)
        user.id, user.guild = 1, SimpleNamespace(id=10)
        user.guild_permissions.administrator = False
        self.interaction = SimpleNamespace(user=user, guild=SimpleNamespace(id=10), guild_id=10,
            channel_id=100, message=SimpleNamespace(id=200),
            response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock(), send_modal=AsyncMock(), is_done=lambda: True),
            followup=SimpleNamespace(send=AsyncMock()))
        self.message = SimpleNamespace(id=200, edit=AsyncMock())
        self.channel = SimpleNamespace(id=100, send=AsyncMock(return_value=self.message),
                                       fetch_message=AsyncMock(return_value=self.message))
        self.service.bot.get_channel.return_value = self.channel

    def modal(self, name='AlexBM'):
        modal = whitelist.NicknameModal(self.service, self.interaction)
        modal.nickname._value = name
        return modal

    async def test_nickname_validation_preserves_original_case(self):
        self.assertEqual(whitelist.validate_nickname('Alex_BM123'), 'Alex_BM123')
        for name in ('ab', 'a' * 17, 'Alex BM', ' Alex', 'Alex\n', '<@123>', 'áléx', 'alex-bm'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                whitelist.validate_nickname(name)

    async def test_one_user_one_nickname_and_case_insensitive_unique(self):
        self.service.change(10, 1, 'AlexBM')
        with self.assertRaises(ValueError):
            self.service.change(10, 1, 'DifferentName')
        with self.assertRaises(ValueError):
            self.service.change(10, 2, 'alexbm')
        self.service.change(11, 2, 'alexbm')
        self.service.change(10, 1, 'Alex_New', editing=True, actor_id=3)
        self.assertEqual(self.service.members['10']['1']['nickname'], 'Alex_New')
        self.assertEqual(self.service.members['10']['1']['updated_by'], 3)
        with self.assertRaises(ValueError):
            self.service.change(10, 99, 'NewName', editing=True)

    async def test_exports_all_pages_with_only_newlines_and_original_or_lowercase(self):
        names = [f'Player_{index}' for index in range(22)]
        for index, name in enumerate(names):
            self.service.change(10, index, name)
        self.assertEqual(self.service.export(10), '\n'.join(names))
        self.assertEqual(self.service.export(10, True), '\n'.join(name.lower() for name in names))
        self.assertEqual(self.service.export(99), '')

    async def test_panel_uses_banner_numbers_native_title_and_unique_emojis(self):
        for index in range(22):
            self.service.change(10, index, f'Player_{index}')
        for page in range(3):
            embed, actual_page, pages = whitelist.render_panel(self.service.members['10'], page)
            data = embed.to_dict()
            self.assertEqual(actual_page, page)
            self.assertEqual(pages, 3)
            self.assertEqual(data['image']['url'], whitelist.BANNER)
            self.assertEqual(data['footer']['text'], BRAND_FOOTER)
            ids = CUSTOM_EMOJI_PATTERN.findall(data['title'] + data['description'])
            self.assertEqual(len(ids), len(set(ids)))
            self.assertLess(len(data['description']), 4096)
        _, page, pages = whitelist.render_panel({}, 999)
        self.assertEqual((page, pages), (0, 1))

    async def test_registration_updates_panel_and_persists_once(self):
        modal = self.modal()
        await modal.on_submit(self.interaction)
        self.assertTrue(modal.submitted)
        self.assertEqual(self.service.members['10']['1']['nickname'], 'AlexBM')
        self.message.edit.assert_awaited_once()
        self.interaction.response.defer.assert_awaited_once()
        await modal.on_submit(self.interaction)
        self.message.edit.assert_awaited_once()

    async def test_concurrent_forms_do_not_register_twice(self):
        first, second = self.modal(), self.modal('OtherNickname')
        await asyncio.gather(first.on_submit(self.interaction), second.on_submit(self.interaction))
        self.assertEqual(len(self.service.members['10']), 1)
        self.assertEqual(self.service.members['10']['1']['nickname'], 'AlexBM')

    async def test_expired_wrong_user_and_stale_panel_rejected(self):
        modal = self.modal()
        modal.user_id = 2
        await modal.on_submit(self.interaction)
        modal.user_id, modal.deadline = 1, time.monotonic() - 1
        await modal.on_submit(self.interaction)
        modal.deadline = time.monotonic() + 180
        self.service.config['10']['message_id'] = 999
        await modal.on_submit(self.interaction)
        self.assertEqual(self.service.members, {})

    async def test_existing_member_cannot_open_second_registration(self):
        self.service.change(10, 1, 'AlexBM')
        view = whitelist.WhitelistView(self.service, 10)
        await view.register.callback(self.interaction)
        self.interaction.response.send_modal.assert_not_awaited()
        self.interaction.response.send_message.assert_awaited_once()

    async def test_panel_buttons_are_persistent_and_restore_after_restart(self):
        self.service.restore()
        self.service.bot.add_view.assert_called_once()
        view = self.service.bot.add_view.call_args.args[0]
        self.assertTrue(view.is_persistent())
        self.assertTrue(all(button.emoji.id for button in view.children))
        await self.service.on_ready()
        self.message.edit.assert_awaited_once()
        self.channel.send.assert_not_awaited()

    async def test_deleted_panel_is_recreated(self):
        self.channel.fetch_message.side_effect = discord.NotFound(SimpleNamespace(status=404, reason='Not Found'), 'Deleted')
        await self.service.on_ready()
        self.channel.send.assert_awaited_once()
        self.assertNotIn('delete_after', self.channel.send.await_args.kwargs)

    async def test_data_survives_panel_update_failure(self):
        self.channel.fetch_message.side_effect = discord.Forbidden(SimpleNamespace(status=403, reason='Forbidden'), 'Denied')
        with self.assertLogs(level='ERROR'):
            await self.modal().on_submit(self.interaction)
        self.assertEqual(self.service.members['10']['1']['nickname'], 'AlexBM')
        self.assertIn('sincronizar', self.interaction.followup.send.await_args.args[0])

    async def test_administration_commands_reject_non_admins(self):
        bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())
        try:
            with patch('whitelist.read_json', return_value={}):
                whitelist.setup(bot)
            group = bot.tree.get_command('whitelist')
            for name in ('configurar', 'agregar', 'editar', 'eliminar', 'sincronizar', 'exportar', 'exportar_minusculas'):
                command = group.get_command(name)
                self.assertIsNotNone(command)
                self.interaction.permissions = discord.Permissions.none()
                with self.assertRaises(discord.app_commands.MissingPermissions):
                    command.checks[0](self.interaction)
                self.interaction.permissions = discord.Permissions(administrator=True)
                self.assertTrue(command.checks[0](self.interaction))
        finally:
            await bot.close()


if __name__ == '__main__':
    unittest.main()
