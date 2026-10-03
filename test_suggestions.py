import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

import suggestions as module


class SuggestionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        with patch('suggestions.read_json', return_value={}):
            self.service = module.SuggestionService(MagicMock())
        self.service.save = MagicMock()
        self.service.sync = AsyncMock()
        self.service.config = {'10': {'enabled': True, 'public_channel_id': 100,
                                     'staff_channel_id': 200, 'review_role_id': 30}}
        self.record = {'id': 'abc', 'guild_id': 10, 'author_id': 1, 'title': 'Idea',
                       'description': 'Una mejora', 'created_at': time.time() - 200,
                       'status': 'pending', 'votes': {}, 'public_channel_id': 100,
                       'staff_channel_id': 200, 'public_message_id': 111, 'staff_message_id': 222}
        self.service.records = {'abc': self.record}

    def interaction(self, user_id=2, staff=False):
        user = MagicMock(spec=discord.Member)
        user.id = user_id
        user.guild = SimpleNamespace(id=10)
        user.roles = [SimpleNamespace(id=30)] if staff else []
        return SimpleNamespace(user=user, guild_id=10, channel_id=200 if staff else 100,
                               message=SimpleNamespace(id=222 if staff else 111),
                               response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock(), send_modal=AsyncMock()),
                               followup=SimpleNamespace(send=AsyncMock()))

    async def test_one_vote_change_and_withdraw(self):
        interaction = self.interaction()
        with patch('suggestions.time.time', return_value=100):
            await self.service.vote(interaction, 'abc', 1)
        self.assertEqual(module.count_votes(self.record), (1, 0))
        with patch('suggestions.time.time', return_value=106):
            await self.service.vote(interaction, 'abc', -1)
        self.assertEqual(module.count_votes(self.record), (0, 1))
        with patch('suggestions.time.time', return_value=112):
            await self.service.vote(interaction, 'abc', -1)
        self.assertEqual(module.count_votes(self.record), (0, 0))

    async def test_fast_vote_click_does_not_change_state(self):
        interaction = self.interaction()
        with patch('suggestions.time.time', return_value=100):
            await self.service.vote(interaction, 'abc', 1)
            await self.service.vote(interaction, 'abc', -1)
        self.assertEqual(module.count_votes(self.record), (1, 0))
        self.service.sync.assert_awaited_once()

    async def test_wrong_message_and_guild_rejected(self):
        interaction = self.interaction()
        interaction.message.id = 999
        await self.service.vote(interaction, 'abc', 1)
        interaction.message.id = 111
        interaction.guild_id = 11
        await self.service.vote(interaction, 'abc', 1)
        self.assertEqual(self.record['votes'], {})

    async def test_staff_role_required_even_for_admin(self):
        interaction = self.interaction()
        interaction.user.guild_permissions = SimpleNamespace(administrator=True)
        interaction.channel_id = 200
        await self.service.review(interaction, 'abc', 'accepted', '')
        self.assertEqual(self.record['status'], 'pending')
        self.service.save.assert_not_called()

    async def test_decision_changes_color_and_closes_votes(self):
        interaction = self.interaction(staff=True)
        await self.service.review(interaction, 'abc', 'accepted', 'Buena idea')
        self.assertEqual(module.render(self.record).color.value, module.COLORS['accepted'])
        self.assertTrue(all(child.disabled for child in module.VoteView(self.service, 'abc').children))
        await self.service.vote(self.interaction(), 'abc', 1)
        self.assertEqual(self.record['votes'], {})
        await self.service.review(interaction, 'abc', 'denied', 'Otra decision')
        self.assertEqual(self.record['status'], 'accepted')

    async def test_denial_reason_and_red_color(self):
        await self.service.review(self.interaction(staff=True), 'abc', 'denied', 'No corresponde')
        self.assertEqual(self.record['reason'], 'No corresponde')
        self.assertEqual(module.render(self.record).color.value, module.COLORS['denied'])

    async def test_delete_removes_both_messages_retains_audit(self):
        public, staff = MagicMock(), MagicMock()
        public.get_partial_message.return_value.delete = AsyncMock()
        staff.get_partial_message.return_value.delete = AsyncMock()
        self.service.channel = AsyncMock(side_effect=[public, staff])
        await self.service.review(self.interaction(staff=True), 'abc', 'deleted', 'Spam')
        self.assertEqual(self.record['status'], 'deleted')
        public.get_partial_message.return_value.delete.assert_awaited_once()
        staff.get_partial_message.return_value.delete.assert_awaited_once()
        self.assertEqual(self.record['reviewer_id'], 2)

    async def test_persistent_views_restore_and_embed_limits(self):
        self.service.restore()
        self.assertEqual(self.service.bot.add_view.call_count, 2)
        for call in self.service.bot.add_view.call_args_list:
            self.assertTrue(call.args[0].is_persistent())
        for status in module.STATUS:
            self.record['status'] = status
            self.record['title'] = '*' * 150
            self.record['description'] = 'x' * 2400
            self.record['reason'] = 'x' * 500
            self.record['reviewer_id'] = 2
            embed = module.render(self.record, staff=True)
            self.assertLessEqual(len(embed), 6000)
            self.assertLessEqual(len(embed.description), 4096)
            self.assertTrue(all(len(field.value) <= 1024 for field in embed.fields))

    async def test_form_only_author_can_open(self):
        source = SimpleNamespace(author=SimpleNamespace(id=1), guild=SimpleNamespace(id=10), content='idea')
        view = module.FormView(self.service, source)
        interaction = self.interaction(user_id=2)
        await view.complete.callback(interaction)
        interaction.response.send_modal.assert_not_awaited()
        interaction.response.send_message.assert_awaited_once()

    async def test_publish_replay_and_partial_delivery_saved(self):
        source = SimpleNamespace(author=SimpleNamespace(id=1), guild=SimpleNamespace(id=10),
                                 channel=SimpleNamespace(id=100), content='idea')
        view = module.FormView(self.service, source)
        self.service.requests[(10, 1)] = view
        self.service.sync.side_effect = discord.Forbidden(SimpleNamespace(status=403, reason='Forbidden'), 'No permission')
        interaction = self.interaction(user_id=1)
        with self.assertLogs(level='ERROR'):
            await self.service.publish(interaction, view, 'Idea', 'Una mejora')
        self.assertEqual(len(self.service.records), 2)
        await self.service.publish(interaction, view, 'Idea', 'Duplicada')
        self.assertEqual(len(self.service.records), 2)
        self.service.sync.assert_awaited_once()

    async def test_completed_form_publishes_then_cleans_original_messages(self):
        source = SimpleNamespace(author=SimpleNamespace(id=1), guild=SimpleNamespace(id=10),
                                 channel=SimpleNamespace(id=100), content='idea', delete=AsyncMock())
        view = module.FormView(self.service, source)
        view.message = SimpleNamespace(delete=AsyncMock())
        self.service.requests[(10, 1)] = view
        interaction = self.interaction(user_id=1)
        async def publish(record):
            interaction.response.defer.assert_awaited_once()
            source.delete.assert_not_awaited()
            record['public_message_id'] = 333
            record['staff_message_id'] = 444
        self.service.sync.side_effect = publish
        await self.service.publish(interaction, view, 'Idea', 'Una mejora')
        source.delete.assert_awaited_once()
        view.message.delete.assert_awaited_once()
        self.assertEqual(len(self.service.records), 2)
        self.assertTrue(view.submitted)

    async def test_expired_form_cannot_publish_and_retains_source(self):
        source = SimpleNamespace(author=SimpleNamespace(id=1), guild=SimpleNamespace(id=10),
                                 channel=SimpleNamespace(id=100), content='idea', delete=AsyncMock())
        view = module.FormView(self.service, source)
        view.deadline = time.monotonic() - 1
        self.service.requests[(10, 1)] = view
        await self.service.publish(self.interaction(user_id=1), view, 'Idea', 'Una mejora')
        self.assertEqual(len(self.service.records), 1)
        source.delete.assert_not_awaited()
        self.service.sync.assert_not_awaited()

    async def test_timeout_cleans_only_its_own_prompt(self):
        source = SimpleNamespace(author=SimpleNamespace(id=1), guild=SimpleNamespace(id=10), content='idea')
        view = module.FormView(self.service, source)
        view.message = SimpleNamespace(delete=AsyncMock())
        newer = object()
        self.service.requests[(10, 1)] = newer
        await view.on_timeout()
        self.assertIs(self.service.requests[(10, 1)], newer)
        view.message.delete.assert_awaited_once()

    async def test_second_modal_after_recent_submission_is_rejected(self):
        self.record['created_at'] = time.time()
        source = SimpleNamespace(author=SimpleNamespace(id=1), guild=SimpleNamespace(id=10),
                                 channel=SimpleNamespace(id=100), content='idea')
        view = module.FormView(self.service, source)
        self.service.requests[(10, 1)] = view
        await self.service.publish(self.interaction(user_id=1), view, 'Otra idea', 'Duplicada')
        self.service.sync.assert_not_awaited()
        self.assertEqual(len(self.service.records), 1)

    async def test_setup_registers_commands_without_replacing_message_handler(self):
        bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())
        try:
            with patch('suggestions.read_json', return_value={}):
                module.setup(bot)
            group = bot.tree.get_command('sugerencias')
            self.assertEqual({command.name for command in group.commands}, {'configurar', 'sincronizar', 'desactivar'})
            self.assertIn('on_message', bot.extra_events)
        finally:
            await bot.close()


if __name__ == '__main__':
    unittest.main()
