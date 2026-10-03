import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

import creators
from common import BRAND_FOOTER, CUSTOM_EMOJI_PATTERN


class LinkTests(unittest.IsolatedAsyncioTestCase):
    def test_panel_and_announcements_use_requested_banner_and_purple(self):
        user = SimpleNamespace(mention='<@1>')
        embeds = [creators.render_panel()]
        for platform in creators.PLATFORM_EMOJIS:
            for kind in ('directo', 'video'):
                embeds.append(creators.render_announcement(user, platform, 'https://example.com', kind))
        for embed in embeds:
            self.assertEqual(embed.color.value, 0x9B59B6)
            self.assertEqual(embed.image.url, creators.CREATOR_BANNER)
            self.assertEqual(embed.footer.text, BRAND_FOOTER)

    def test_announcement_uses_discord_avatar_and_custom_copy(self):
        user = SimpleNamespace(mention='<@1>', display_name='Alex',
                               display_avatar=SimpleNamespace(url='https://cdn.discordapp.com/avatars/1/avatar.png'))
        embed = creators.render_announcement(user, 'YouTube', 'https://youtu.be/Abcd1234_-x', 'video', 'Mi nuevo video', 'Una partida especial')
        self.assertEqual(embed.thumbnail.url, user.display_avatar.url)
        self.assertEqual(embed.author.icon_url, user.display_avatar.url)
        self.assertEqual(embed.author.name, 'Alex')
        self.assertIn('Mi nuevo video', embed.title)
        self.assertIn('Una partida especial', embed.description)
        self.assertNotIn('[Ver', embed.description)
        self.assertEqual(embed.url, 'https://youtu.be/Abcd1234_-x')

    async def test_announcement_link_button_uses_validated_destination(self):
        url = 'https://twitch.tv/creator'
        view = creators.announcement_link_view('Twitch', url, 'directo')
        self.assertEqual(view.children[0].url, url)
        self.assertEqual(view.children[0].label, 'Ver directo')
        self.assertEqual(view.children[0].style, discord.ButtonStyle.link)

    def test_allowed_direct_links(self):
        for url, platform in (
            ('https://www.youtube.com/@creator/live', 'YouTube'),
            ('https://youtu.be/Abcd1234_-x', 'YouTube'),
            ('https://www.twitch.tv/creator', 'Twitch'),
            ('https://kick.com/creator', 'Kick'),
            ('https://www.tiktok.com/@creator/live', 'TikTok'),
        ):
            with self.subTest(url=url):
                self.assertEqual(creators.validate_link(url, 'directo')[0], platform)

    def test_allowed_video_links(self):
        for url, platform in (
            ('https://www.youtube.com/watch?v=Abcd1234_-x', 'YouTube'),
            ('https://www.youtube.com/shorts/Abcd1234_-x', 'YouTube'),
            ('https://www.twitch.tv/videos/123456', 'Twitch'),
            ('https://clips.twitch.tv/Example-Clip', 'Twitch'),
            ('https://www.twitch.tv/creator/clip/Example-Clip', 'Twitch'),
            ('https://kick.com/creator/videos/abcdef-1234', 'Kick'),
            ('https://kick.com/creator?clip=clip_abcdef', 'Kick'),
            ('https://www.tiktok.com/@creator/video/1234567890', 'TikTok'),
        ):
            with self.subTest(url=url):
                self.assertEqual(creators.validate_link(url, 'video')[0], platform)

    def test_spoofed_hosts_credentials_ports_and_nonvideos_rejected(self):
        for url in (
            'https://youtube.com.evil.test/watch?v=Abcd1234_-x',
            'https://youtube.com@evil.test/watch?v=Abcd1234_-x',
            'https://evil.test@youtube.com/watch?v=Abcd1234_-x',
            'https://youtube.com:443/watch?v=Abcd1234_-x',
            'http://youtube.com/watch?v=Abcd1234_-x',
            'https://127.0.0.1/video/123', 'https://youtube.com/watch?v=bad',
            'https://youtube.com/watch?v=Abcd1234_-x&v=Abcd1234_-x',
            'https://www.twitch.tv/creator', 'https://kick.com/creator',
            'https://www.tiktok.com/@creator', 'https://vt.tiktok.com/abc',
            'https://youtube.com/watch?v=Abcd1234_-x#fragment',
            'https://youtube.com/watch?v=Abcd1234_-x)@everyone',
            'https://youtube.com\\evil.test/watch?v=Abcd1234_-x',
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                creators.validate_link(url, 'video')

    def test_wrong_live_route_rejected(self):
        for url in ('https://twitch.tv/videos/123', 'https://kick.com/login',
                    'https://tiktok.com/@creator/video/123'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                creators.validate_link(url, 'directo')


class CreatorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        with patch('creators.read_json', return_value={}):
            self.service = creators.CreatorService(MagicMock())
        self.service.config = {'10': {'enabled': True, 'channel_id': 100, 'role_ids': [30, 40], 'cooldown': 300}}
        self.user = MagicMock(spec=discord.Member)
        self.user.id = 1
        self.user.mention = '<@1>'
        self.user.guild = SimpleNamespace(id=10)
        self.user.guild_permissions = SimpleNamespace(administrator=False)
        self.user.roles = [SimpleNamespace(id=30)]
        self.channel = SimpleNamespace(id=100, mention='<#100>', send=AsyncMock(return_value=SimpleNamespace(id=200)))
        self.service.bot.get_channel.return_value = self.channel
        self.interaction = SimpleNamespace(user=self.user, guild_id=10, channel_id=100,
            response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock(), send_modal=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()))
        self.modal = SimpleNamespace(author_id=1, guild_id=10, channel_id=100,
            deadline=time.monotonic() + 180, submitted=False, kind='video',
            link=SimpleNamespace(value='https://www.youtube.com/watch?v=Abcd1234_-x'))

    async def test_roles_channel_guild_admin_and_disabled_system(self):
        self.assertTrue(self.service.authorized(self.user, 10, 100))
        self.assertFalse(self.service.authorized(self.user, 10, 999))
        self.user.roles = [SimpleNamespace(id=40)]
        self.assertTrue(self.service.authorized(self.user, 10, 100))
        self.user.roles = []
        self.assertFalse(self.service.authorized(self.user, 10, 100))
        self.user.guild_permissions.administrator = True
        self.assertTrue(self.service.authorized(self.user, 10, 999))
        self.assertFalse(self.service.authorized(self.user, 11, 100))
        self.service.config['10']['enabled'] = False
        self.assertFalse(self.service.authorized(self.user, 10, 100))

    async def test_panel_has_two_buttons_platform_emojis_and_no_repeats(self):
        await self.service.panel(self.user, 10, self.channel)
        kwargs = self.channel.send.await_args.kwargs
        self.assertEqual(len(kwargs['view'].children), 2)
        data = kwargs['embed'].to_dict()
        self.assertEqual(data['footer']['text'], BRAND_FOOTER)
        text = data['description'] + ''.join(field['value'] for field in data['fields'])
        ids = CUSTOM_EMOJI_PATTERN.findall(text)
        self.assertEqual(len(ids), len(set(ids)))
        for emoji in creators.PLATFORM_EMOJIS.values():
            self.assertIn(emoji, text)
        await self.service.panel(self.user, 10, self.channel)
        self.channel.send.assert_awaited_once()

    async def test_owner_only_button_and_role_recheck(self):
        view = creators.CreatorView(self.service, 2, 10, 100)
        await view.live.callback(self.interaction)
        self.interaction.response.send_modal.assert_not_awaited()
        view.author_id = 1
        await view.live.callback(self.interaction)
        self.interaction.response.send_modal.assert_awaited_once()
        self.user.roles = []
        with patch('creators.write_json'):
            await self.service.publish(self.interaction, self.modal)
        self.channel.send.assert_not_awaited()

    async def test_publish_persisted_and_duplicate_form_rejected(self):
        with patch('creators.write_json') as save:
            await self.service.publish(self.interaction, self.modal)
            await self.service.publish(self.interaction, self.modal)
        self.channel.send.assert_awaited_once()
        self.assertTrue(self.modal.submitted)
        self.assertEqual(self.service.announcements['10:1']['platform'], 'YouTube')
        save.assert_called_once()
        self.interaction.response.defer.assert_awaited()

    async def test_concurrent_forms_only_publish_once(self):
        import asyncio
        second = SimpleNamespace(**vars(self.modal))
        with patch('creators.write_json'):
            await asyncio.gather(self.service.publish(self.interaction, self.modal),
                                 self.service.publish(self.interaction, second))
        self.channel.send.assert_awaited_once()

    async def test_invalid_link_and_expired_form_not_published(self):
        self.modal.link.value = 'https://evil.test/video/1'
        await self.service.publish(self.interaction, self.modal)
        self.modal.link.value = 'https://youtu.be/Abcd1234_-x'
        self.modal.deadline = time.monotonic() - 1
        await self.service.publish(self.interaction, self.modal)
        self.channel.send.assert_not_awaited()

    async def test_persistent_cooldown_survives_reload(self):
        state = {'10:1': {'created_at': time.time()}}
        with patch('creators.read_json', side_effect=[self.service.config, state]):
            self.service = creators.CreatorService(self.service.bot)
        await self.service.publish(self.interaction, self.modal)
        self.channel.send.assert_not_awaited()

    async def test_failed_send_does_not_consume_form_or_cooldown(self):
        self.channel.send.side_effect = discord.Forbidden(SimpleNamespace(status=403, reason='Forbidden'), 'Denied')
        with self.assertLogs(level='ERROR'), patch('creators.write_json') as save:
            await self.service.publish(self.interaction, self.modal)
        self.assertFalse(self.modal.submitted)
        self.assertEqual(self.service.announcements, {})
        save.assert_not_called()

    async def test_all_command_variants_registered(self):
        bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())
        try:
            with patch('creators.read_json', return_value={}):
                creators.setup(bot)
            for name in ('directo', 'video'):
                self.assertIsNotNone(bot.tree.get_command(name))
                self.assertIsNotNone(bot.get_command(name))
            self.assertIsNotNone(bot.tree.get_command('creadores').get_command('configurar'))
        finally:
            await bot.close()


if __name__ == '__main__':
    unittest.main()
